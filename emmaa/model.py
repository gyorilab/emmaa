import yaml
import json
import time
import boto3
import pickle
import logging
from botocore.handlers import disable_signing
from indra.databases import ndex_client
import indra.tools.assemble_corpus as ac
from indra.literature import pubmed_client
from indra.statements import stmts_to_json
from indra.assemblers.cx import CxAssembler
from indra.assemblers.pysb import PysbAssembler
from emmaa.priors import SearchTerm
from emmaa.util import make_date_str, find_latest_s3_file
from emmaa.readers.aws_reader import read_pmid_search_terms
from emmaa.readers.db_client_reader import read_db_pmid_search_terms


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
        A list of SearchTerm objects containing the search terms used in the model
    ndex_network : str
        The identifier of the NDEx network corresponding to the model.
    """
    def __init__(self, name, config):
        self.name = name
        self.stmts = []
        self.search_terms = []
        self.ndex_network = None
        self._load_config(config)

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
        self.ndex_network = config['ndex']['network']

    def search_literature(self, date_limit=None):
        """Search for the model's search terms in the literature.

        Parameters
        ----------
        date_limit : Optional[int]
            The number of days to search back from today.

        Returns
        -------
        pmid_to_terms : dict
            A dict representing all the PMIDs returned by the searches as keys,
            and the search terms for which the given PMID was produced as
            values.
        """
        term_to_pmids = {}
        for term in self.search_terms:
            pmids = pubmed_client.get_ids(term.search_term, reldate=date_limit)
            logger.info(f'{len(pmids)} PMIDs found for {term.search_term}')
            term_to_pmids[term] = pmids
            time.sleep(0.5)
        pmid_to_terms = {}
        for term, pmids in term_to_pmids.items():
            for pmid in pmids:
                try:
                    pmid_to_terms[pmid].append(term)
                except KeyError:
                    pmid_to_terms[pmid] = [term]
        return pmid_to_terms

    def get_new_readings(self, run_reading=False, date_limit=10):
        """Search new literature, read, and add to model statements"""
        pmid_to_terms = self.search_literature(date_limit=date_limit)
        if run_reading:
            estmts = read_pmid_search_terms(pmid_to_terms)
        else:
            estmts = read_db_pmid_search_terms(pmid_to_terms)
        self.extend_unique(estmts)

    def extend_unique(self, estmts):
        """Extend model statements only if it is not already there."""
        source_hashes = {est.stmt.get_hash(shallow=False)
                         for est in self.stmts}
        for estmt in estmts:
            if estmt.stmt.get_hash(shallow=False) not in source_hashes:
                self.stmts.append(estmt)

    def run_assembly(self):
        """Run INDRA's assembly pipeline on the Statements.

        Returns
        -------
        stmts : list[indra.statements.Statement]
            The list of assembled INDRA Statements.
        """
        stmts = self.get_indra_stmts()
        stmts = ac.filter_no_hypothesis(stmts)
        stmts = ac.map_grounding(stmts)
        stmts = ac.map_sequence(stmts)
        stmts = ac.filter_human_only(stmts)
        stmts = ac.run_preassembly(stmts, return_toplevel=False)
        return stmts

    def upload_to_ndex(self):
        """Upload the assembled model as CX to NDEx"""
        assembled_stmts = self.run_assembly()
        cxa = CxAssembler(assembled_stmts, network_name=self.name)
        cxa.make_model()
        cx_str = cxa.print_cx()
        ndex_client.update_network(cx_str, self.ndex_network)

    def save_to_s3(self):
        """Dump the model state to S3."""
        date_str = make_date_str()
        fname = f'models/{self.name}/model_{date_str}'
        client = boto3.client('s3')
        client.meta.events.register('chooser-signer.s3.*', disable_signing)
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
            file at 'models/{model_name}/config.yaml'.

        Returns
        -------
        emmaa.model.EmmaaModel
            Latest instance of EmmaaModel with the given name, loaded from S3.
        """
        base_key = f'models/{model_name}'
        config_key = f'{base_key}/config.yaml'
        latest_model_key = find_latest_s3_file('emmaa', f'{base_key}/model_',
                                               extension='.pkl')
        client = boto3.client('s3')
        client.meta.events.register('chooser-signer.s3.*', disable_signing)
        logger.info(f'Loading model config from {config_key}')
        obj = client.get_object(Bucket='emmaa', Key=config_key)
        config = yaml.load(obj['Body'].read().decode('utf8'))
        logger.info(f'Loading model state from {latest_model_key}')
        obj = client.get_object(Bucket='emmaa', Key=latest_model_key)
        stmts = pickle.loads(obj['Body'].read())
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

    def assemble_pysb(self):
        """Assemble the model into PySB and return the assembled model."""
        stmts = self.get_indra_stmts()
        pa = PysbAssembler()
        pa.add_statements(stmts)
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
