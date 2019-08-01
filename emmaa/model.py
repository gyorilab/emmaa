import json
import time
import pickle
import logging
import datetime
from indra.databases import ndex_client
import indra.tools.assemble_corpus as ac
from indra.literature import pubmed_client, elsevier_client
from indra.assemblers.cx import CxAssembler
from indra.assemblers.pysb import PysbAssembler
from indra.mechlinker import MechLinker
from indra.preassembler.hierarchy_manager import get_wm_hierarchies
from indra.preassembler import Preassembler
from indra.belief.wm_scorer import get_eidos_scorer
from indra.statements import Event, Association
from emmaa.priors import SearchTerm
from emmaa.readers.aws_reader import read_pmid_search_terms
from emmaa.readers.db_client_reader import read_db_pmid_search_terms
from emmaa.readers.elsevier_eidos_reader import \
    read_elsevier_eidos_search_terms
from emmaa.util import make_date_str, find_latest_s3_file, get_s3_client


logger = logging.getLogger(__name__)


class EmmaaModel(object):
    """"Represents an EMMAA model.

    Parameters
    ----------
    name : str
        The name of the model.
    config : dict
        A configuration dict that is typically loaded from a YAML file.

    Attributes
    ----------
    name : str
        A string containing the name of the model
    stmts : list[emmaa.EmmaaStatement]
        A list of EmmaaStatement objects representing the model
    search_terms : list[emmaa.priors.SearchTerm]
        A list of SearchTerm objects containing the search terms used in the
        model.
    ndex_network : str
        The identifier of the NDEx network corresponding to the model.
    assembled_stmts : list[indra.statements.Statement]
        A list of assembled INDRA Statements
    """
    def __init__(self, name, config):
        self.name = name
        self.stmts = []
        self.assembly_config = {}
        self.test_config = {}
        self.reading_config = {}
        self.search_terms = []
        self.ndex_network = None
        self._load_config(config)
        self.assembled_stmts = []

    def add_statements(self, stmts):
        """"Add a set of EMMAA Statements to the model

        Parameters
        ----------
        stmts : list[emmaa.EmmaaStatement]
            A list of EMMAA Statements to add to the model
        """
        self.stmts += stmts

    def get_indra_stmts(self):
        """Return the INDRA Statements contained in the model.

        Returns
        -------
        list[indra.statements.Statement]
            The list of INDRA Statements that are extracted from the EMMAA
            Statements.
        """
        return [es.stmt for es in self.stmts]

    def _load_config(self, config):
        self.search_terms = [SearchTerm.from_json(s) for s in
                             config['search_terms']]
        if 'ndex' in config:
            self.ndex_network = config['ndex']['network']
        else:
            self.ndex_network = None
        if 'reading' in config:
            self.reading_config = config['reading']
        if 'assembly' in config:
            self.assembly_config = config['assembly']
        if 'test' in config:
            self.test_config = config['test']

    def search_literature(self, date_limit=None):
        """Search for the model's search terms in the literature.

        Parameters
        ----------
        date_limit : Optional[int]
            The number of days to search back from today.

        Returns
        -------
        ids_to_terms : dict
            A dict representing all the literature source IDs (e.g.,
            PMIDs or PIIS) returned by the searches as keys,
            and the search terms for which the given ID was produced as
            values.
        """
        lit_source = self.reading_config.get('literature_source', 'pubmed')
        if lit_source == 'pubmed':
            terms_to_ids = self.search_pubmed(self.search_terms, date_limit)
        elif lit_source == 'elsevier':
            terms_to_ids = self.search_elsevier(self.search_terms, date_limit)
        else:
            raise ValueError('Unknown literature source: %s' % lit_source)
        ids_to_terms = {}
        for term, ids in terms_to_ids.items():
            for id in ids:
                try:
                    ids_to_terms[id].append(term)
                except KeyError:
                    ids_to_terms[id] = [term]
        return ids_to_terms

    @staticmethod
    def search_pubmed(search_terms, date_limit):
        """Search PubMed for given search terms.

        Parameters
        ----------
        search_terms : list[emmaa.priors.SearchTerm]
            A list of SearchTerm objects to search PubMed for.
        date_limit : int
            The number of days to search back from today.

        Returns
        -------
        terms_to_pmids : dict
            A dict representing given search terms as keys and PMIDs returned
            by searches as values.
        """
        terms_to_pmids = {}
        for term in search_terms:
            pmids = pubmed_client.get_ids(term.search_term, reldate=date_limit)
            logger.info(f'{len(pmids)} PMIDs found for {term.search_term}')
            terms_to_pmids[term] = pmids
            time.sleep(0.5)
        return terms_to_pmids

    @staticmethod
    def search_elsevier(search_terms, date_limit):
        """Search Elsevier for given search terms.

        Parameters
        ----------
        search_terms : list[emmaa.priors.SearchTerm]
            A list of SearchTerm objects to search PubMed for.
        date_limit : int
            The number of days to search back from today.

        Returns
        -------
        terms_to_piis : dict
            A dict representing given search terms as keys and PIIs returned
            by searches as values.
        """
        start_date = (
            datetime.datetime.utcnow() - datetime.timedelta(days=date_limit))
        start_date = start_date.isoformat(timespec='seconds') + 'Z'
        terms_to_piis = {}
        for term in search_terms:
            # NOTE for now limiting the search to only 5 PIIs
            piis = elsevier_client.get_piis_for_date(
                term.search_term, loaded_after=start_date)[:5]
            logger.info(f'{len(piis)} PIIs found for {term.search_term}')
            terms_to_piis[term] = piis
        return terms_to_piis

    def get_new_readings(self, date_limit=10):
        """Search new literature, read, and add to model statements"""
        reader = self.reading_config.get('reader', 'indra_db')
        ids_to_terms = self.search_literature(date_limit=date_limit)
        if reader == 'aws':
            estmts = read_pmid_search_terms(ids_to_terms)
        elif reader == 'indra_db':
            estmts = read_db_pmid_search_terms(ids_to_terms)
        elif reader == 'elsevier_eidos':
            estmts = read_elsevier_eidos_search_terms(ids_to_terms)
        else:
            raise ValueError('Unknown reader: %s' % reader)

        self.extend_unique(estmts)

    def extend_unique(self, estmts):
        """Extend model statements only if it is not already there."""
        source_hashes = {est.stmt.get_hash(shallow=False, refresh=True)
                         for est in self.stmts}
        for estmt in estmts:
            if estmt.stmt.get_hash(shallow=False, refresh=True) not in \
                    source_hashes:
                self.stmts.append(estmt)

    def eliminate_copies(self):
        """Filter out exact copies of the same Statement."""
        logger.info('Starting with %d raw EmmaaStatements' % len(self.stmts))
        self.stmts = list({estmt.stmt.get_hash(shallow=False, refresh=True):
                           estmt for estmt in self.stmts}.values())
        logger.info(('Continuing with %d raw EmmaaStatements'
                     ' that are not exact copies') % len(self.stmts))

    def run_assembly(self):
        """Run INDRA's assembly pipeline on the Statements."""
        self.eliminate_copies()
        stmts = self.get_indra_stmts()
        stmts = self.filter_event_association(stmts)
        stmts = ac.filter_no_hypothesis(stmts)
        if not self.assembly_config.get('skip_map_grounding'):
            stmts = ac.map_grounding(stmts)
        if self.assembly_config.get('standardize_names'):
            ac.standardize_names_groundings(stmts)
        if self.assembly_config.get('filter_ungrounded'):
            score_threshold = self.assembly_config.get('score_threshold')
            stmts = ac.filter_grounded_only(
                stmts, score_threshold=score_threshold)
        if self.assembly_config.get('merge_groundings'):
            stmts = ac.merge_groundings(stmts)
        if self.assembly_config.get('merge_deltas'):
            stmts = ac.merge_deltas(stmts)
        relevance_policy = self.assembly_config.get('filter_relevance')
        if relevance_policy:
            stmts = self.filter_relevance(stmts, relevance_policy)
        if not self.assembly_config.get('skip_filter_human'):
            stmts = ac.filter_human_only(stmts)
        if not self.assembly_config.get('skip_map_sequence'):
            stmts = ac.map_sequence(stmts)
        # Use WM hierarchies and belief scorer for WM preassembly
        preassembly_mode = self.assembly_config.get('preassembly_mode')
        if preassembly_mode == 'wm':
            hierarchies = get_wm_hierarchies()
            belief_scorer = get_eidos_scorer()
            stmts = ac.run_preassembly(
                stmts, return_toplevel=False, belief_scorer=belief_scorer,
                hierarchies=hierarchies)
        else:
            stmts = ac.run_preassembly(stmts, return_toplevel=False)
        belief_cutoff = self.assembly_config.get('belief_cutoff')
        if belief_cutoff is not None:
            stmts = ac.filter_belief(stmts, belief_cutoff)
        stmts = ac.filter_top_level(stmts)

        if self.assembly_config.get('filter_direct'):
            stmts = ac.filter_direct(stmts)
            stmts = ac.filter_enzyme_kinase(stmts)
            stmts = ac.filter_mod_nokinase(stmts)
            stmts = ac.filter_transcription_factor(stmts)

        if self.assembly_config.get('mechanism_linking'):
            ml = MechLinker(stmts)
            ml.gather_explicit_activities()
            ml.reduce_activities()
            ml.gather_modifications()
            ml.reduce_modifications()
            ml.gather_explicit_activities()
            ml.replace_activations()
            ml.require_active_forms()
            stmts = ml.statements

        self.assembled_stmts = stmts

    def filter_event_association(self, stmts):
        """Filter a list of Statements to exclude Events and Associations."""
        logger.info('Filtering Events and Associations.')
        stmts = [stmt for stmt in stmts if (
            (not isinstance(stmt, Event)) and
            (not isinstance(stmt, Association)))]
        logger.info('%d statements after filter...' % len(stmts))
        return stmts

    def filter_relevance(self, stmts, policy=None):
        """Filter a list of Statements to ones matching a search term."""
        logger.info('Filtering %d statements for relevance...' % len(stmts))
        stmts_out = []
        stnames = {s.name for s in self.search_terms}
        for stmt in stmts:
            agnames = {a.name for a in stmt.agent_list() if a is not None}
            if policy == 'prior_one' and (agnames & stnames):
                stmts_out.append(stmt)
            elif policy == 'prior_all' and agnames.issubset(stnames):
                stmts_out.append(stmt)
            elif policy is None:
                stmts_out.append(stmt)
        logger.info('%d statements after filter...' % len(stmts_out))
        return stmts_out

    def update_to_ndex(self):
        """Update assembled model as CX on NDEx, updates existing network."""
        if not self.assembled_stmts:
            self.run_assembly()
        cxa = CxAssembler(self.assembled_stmts, network_name=self.name)
        cxa.make_model()
        cx_str = cxa.print_cx()
        ndex_client.update_network(cx_str, self.ndex_network)

    def upload_to_ndex(self):
        """Upload the assembled model as CX to NDEx, creates new network."""
        if not self.assembled_stmts:
            self.run_assembly()
        cxa = CxAssembler(self.assembled_stmts, network_name=self.name)
        cxa.make_model()
        model_uuid = cxa.upload_model()
        self.ndex_network = model_uuid
        return model_uuid

    def save_to_s3(self):
        """Dump the model state to S3."""
        date_str = make_date_str()
        fname = f'models/{self.name}/model_{date_str}'
        client = get_s3_client()
        # Dump as pickle
        client.put_object(Body=pickle.dumps(self.stmts), Bucket='emmaa',
                          Key=fname+'.pkl')
        # Dump as json
        client.put_object(Body=str.encode(json.dumps(self.to_json()),
                                          encoding='utf8'),
                          Bucket='emmaa', Key=fname+'.json')

    @classmethod
    def load_from_s3(klass, model_name):
        """Load the latest model state from S3.

        Parameters
        ----------
        model_name : str
            Name of model to load. This function expects the latest model
            to be found on S3 in the emmaa bucket with key
            'models/{model_name}/model_{date_string}', and the model config
            file at 'models/{model_name}/config.json'.

        Returns
        -------
        emmaa.model.EmmaaModel
            Latest instance of EmmaaModel with the given name, loaded from S3.
        """
        config = load_config_from_s3(model_name)
        stmts = load_stmts_from_s3(model_name)
        em = klass(model_name, config)
        em.stmts = stmts
        return em

    def get_entities(self):
        """Return a list of Agent objects that the model contains."""
        istmts = self.get_indra_stmts()
        agents = []
        for stmt in istmts:
            agents += [a for a in stmt.agent_list() if a is not None]
        return agents

    def get_assembled_entities(self):
        """Return a list of Agent objects that the assembled model contains."""
        if not self.assembled_stmts:
            self.run_assembly()
        agents = []
        for stmt in self.assembled_stmts:
            agents += [a for a in stmt.agent_list() if a is not None]
        return agents

    def assemble_pysb(self):
        """Assemble the model into PySB and return the assembled model."""
        self.run_assembly()
        pa = PysbAssembler()
        pa.add_statements(self.assembled_stmts)
        pysb_model = pa.make_model()
        return pysb_model

    def to_json(self):
        """Convert the model into a json dumpable dictionary"""
        json_output = {'name': self.name,
                       'ndex_network': self.ndex_network,
                       'search_terms': [st.to_json() for st
                                        in self.search_terms],
                       'stmts': [st.to_json() for st in self.stmts]}
        return json_output

    def __repr__(self):
        return "EmmaModel(%s, %d stmts, %d search terms)" % \
                   (self.name, len(self.stmts), len(self.search_terms))


def load_config_from_s3(model_name):
    """Return a JSON dict of config settings for a model from S3.

    Parameters
    ----------
    model_name : str
        The name of the model whose config should be loaded.

    Returns
    -------
    config : dict
        A JSON dictionary of the model configuration loaded from S3.
    """
    client = get_s3_client()
    base_key = f'models/{model_name}'
    config_key = f'{base_key}/config.json'
    logger.info(f'Loading model config from {config_key}')
    obj = client.get_object(Bucket='emmaa', Key=config_key)
    config = json.loads(obj['Body'].read().decode('utf8'))
    return config


def save_config_to_s3(model_name, config):
    """Upload config settings for a model to S3.

    Parameters
    ----------
    model_name : str
        The name of the model whose config should be saved to S3.
    config : dict
        A JSON dict of configurations for the model.
    """
    client = get_s3_client()
    base_key = f'models/{model_name}'
    config_key = f'{base_key}/config.json'
    logger.info(f'Saving model config to {config_key}')
    client.put_object(Body=str.encode(json.dumps(config, indent=1),
                                      encoding='utf8'),
                      Bucket='emmaa', Key=config_key)


def load_stmts_from_s3(model_name):
    """Return the list of EMMAA Statements constituting the latest model.

    Parameters
    ----------
    model_name : str
        The name of the model whose config should be loaded.

    Returns
    -------
    stmts : list of emmaa.statements.EmmaaStatement
        The list of EMMAA Statements in the latest model version.
    """
    client = get_s3_client()
    base_key = f'models/{model_name}'
    latest_model_key = find_latest_s3_file('emmaa', f'{base_key}/model_',
                                           extension='.pkl')
    logger.info(f'Loading model state from {latest_model_key}')
    obj = client.get_object(Bucket='emmaa', Key=latest_model_key)
    stmts = pickle.loads(obj['Body'].read())
    return stmts
