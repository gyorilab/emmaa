import time
import logging
import datetime
import pybel
from botocore.exceptions import ClientError
from indra.databases import ndex_client
from indra.literature import pubmed_client, elsevier_client, biorxiv_client
from indra.assemblers.cx import CxAssembler
from indra.assemblers.pysb import PysbAssembler
from indra.assemblers.pybel import PybelAssembler
from indra.assemblers.indranet import IndraNetAssembler
from indra.statements import stmts_from_json
from indra.pipeline import AssemblyPipeline, register_pipeline
from indra.tools.assemble_corpus import filter_grounded_only
from indra_db.client.principal.curation import get_curations
from indra_db.util import get_db, _get_trids
from emmaa.priors import SearchTerm
from emmaa.readers.aws_reader import read_pmid_search_terms
from emmaa.readers.db_client_reader import read_db_pmid_search_terms, \
    read_db_doi_search_terms
from emmaa.readers.elsevier_eidos_reader import \
    read_elsevier_eidos_search_terms
from emmaa.util import make_date_str, find_latest_s3_file, strip_out_date, \
    EMMAA_BUCKET_NAME, find_nth_latest_s3_file, load_pickle_from_s3, \
    save_pickle_to_s3, load_json_from_s3, save_json_to_s3, \
    load_gzip_json_from_s3, get_s3_client
from emmaa.statements import to_emmaa_stmts


logger = logging.getLogger(__name__)
register_pipeline(get_curations)


class EmmaaModel(object):
    """Represents an EMMAA model.

    Parameters
    ----------
    name : str
        The name of the model.
    config : dict
        A configuration dict that is typically loaded from a YAML file.
    paper_ids : list(str) or None
        A list of paper IDs used to get statements for the current state of the
        model. With new reading results, new paper IDs will be added. If not
        provided, initial set will be derived from existing statements.

    Attributes
    ----------
    stmts : list[emmaa.EmmaaStatement]
        A list of EmmaaStatement objects representing the model
    assembly_config : dict
        Configurations for assembling the model.
    test_config : dict
        Configurations for running tests on the model.
    reading_config : dict
        Configurations for reading the content.
    query_config : dict
        Configurations for running queries on the model.
    search_terms : list[emmaa.priors.SearchTerm]
        A list of SearchTerm objects containing the search terms used in the
        model.
    ndex_network : str
        The identifier of the NDEx network corresponding to the model.
    assembled_stmts : list[indra.statements.Statement]
        A list of assembled INDRA Statements
    """
    def __init__(self, name, config, paper_ids=None):
        self.name = name
        self.stmts = []
        self.assembly_config = {}
        self.test_config = {}
        self.reading_config = {}
        self.query_config = {}
        self.search_terms = []
        self.ndex_network = None
        self.human_readable_name = None
        self.export_formats = []
        self._load_config(config)
        self.assembled_stmts = []
        if paper_ids:
            self.paper_ids = set(paper_ids)
        else:
            self.paper_ids = set()
        self.date_str = make_date_str()

    def add_statements(self, stmts):
        """Add a set of EMMAA Statements to the model

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
        if 'query' in config:
            self.query_config = config['query']
        if 'human_readable_name' in config:
            self.human_readable_name = config['human_readable_name']
        self.export_formats = config.get('export_formats', [])

    def search_literature(self, lit_source, date_limit=None):
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
        if lit_source == 'pubmed':
            terms_to_ids = self.search_pubmed(self.search_terms, date_limit)
        elif lit_source == 'biorxiv':
            collection_id = self.reading_config.get('collection_id', '181')
            terms_to_ids = self.search_biorxiv(collection_id, date_limit)
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
            time.sleep(1)
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
            time.sleep(1)
        return terms_to_piis

    @staticmethod
    def search_biorxiv(collection_id, date_limit):
        """Search BioRxiv within date_limit.

        Parameters
        ----------
        date_limit : int
            The number of days to search back from today.
        collection_id : str
            ID of a collection to search BioArxiv for.
        Returns
        -------
        terms_to_dois : dict
            A dict representing biorxiv collection ID as key and DOIs returned
            by search as values.
        """
        start_date = (
            datetime.datetime.utcnow() - datetime.timedelta(days=date_limit))
        dois = biorxiv_client.get_collection_dois(collection_id, start_date)
        logger.info(f'{len(dois)} DOIs found')
        term = SearchTerm('other', f'biorxiv: {collection_id}', {}, None)
        terms_to_dois = {term: dois}
        return terms_to_dois

    def get_new_readings(self, date_limit=10):
        """Search new literature, read, and add to model statements"""
        readers = self.reading_config.get('reader', ['indra_db_pmid'])
        lit_sources = self.reading_config.get('literature_source', ['pubmed'])
        if isinstance(lit_sources, str):
            lit_sources = [lit_sources]
        if isinstance(readers, str):
            readers = [readers]
        estmts = []
        for lit_source, reader in zip(lit_sources, readers):
            ids_to_terms = self.search_literature(lit_source, date_limit)
            if reader == 'aws':
                new_estmts = read_pmid_search_terms(
                    ids_to_terms)
                self.add_paper_ids(ids_to_terms.keys(), 'pmid')
            elif reader == 'indra_db_pmid':
                new_estmts = read_db_pmid_search_terms(
                    ids_to_terms)
                self.add_paper_ids(ids_to_terms.keys(), 'pmid')
            elif reader == 'indra_db_doi':
                new_estmts = read_db_doi_search_terms(
                    ids_to_terms)
                self.add_paper_ids(ids_to_terms.keys(), 'doi')
            elif reader == 'elsevier_eidos':
                new_estmts = read_elsevier_eidos_search_terms(
                    ids_to_terms)
                self.add_paper_ids(ids_to_terms.keys(), 'pii')
            else:
                raise ValueError('Unknown reader: %s' % reader)
            estmts += new_estmts
        logger.info('Got a total of %d new EMMAA Statements from reading' %
                    len(estmts))
        self.extend_unique(estmts)
        if self.reading_config.get('cord19_update'):
            self.update_with_cord19()
        self.eliminate_copies()

    def extend_unique(self, estmts):
        """Extend model statements only if it is not already there."""
        source_hashes = {est.stmt.get_hash(shallow=False, refresh=True)
                         for est in self.stmts}
        len_before = len(self.stmts)
        for estmt in estmts:
            if estmt.stmt.get_hash(shallow=False, refresh=True) not in \
                    source_hashes:
                self.stmts.append(estmt)
        len_after = len(self.stmts)
        logger.info('Extended EMMAA Statements by %d new Statements' %
                    (len_after - len_before))

    def update_with_cord19(self):
        """Update model with new CORD19 dataset statements."""
        # Using local import to avoid dependency
        from covid_19.emmaa_update import make_model_stmts
        current_stmts = self.get_indra_stmts()
        default_filenames = [
            'drug_stmts_v2.pkl', 'gordon_ndex_stmts.pkl',
            'virhostnet_stmts.pkl', 'ctd_stmts.pkl']
        if isinstance(self.reading_config['cord19_update'], dict):
            fnames = self.reading_config['cord19_update'].get(
                'filenames', default_filenames)
        else:  # if it's a boolean
            fnames = default_filenames
        other_stmts = []
        for fname in fnames:
            file_stmts = load_pickle_from_s3('indra-covid19', fname)
            logger.info(f'Loaded {len(file_stmts)} statements from {fname}.')
            other_stmts += file_stmts
        new_stmts, paper_ids = make_model_stmts(current_stmts, other_stmts)
        self.stmts = to_emmaa_stmts(new_stmts, datetime.datetime.now(), [])
        self.add_paper_ids(paper_ids, 'TRID')

    def add_paper_ids(self, initial_ids, id_type='pmid'):
        """Convert if needed and save paper IDs.

        Parameters
        ----------
        initial_ids : set(str)
            A set of paper IDs.
        id_type : str
            What type the given IDs are (e.g. pmid, doi, pii). All IDs except
            for PIIs will be converted into TextRef IDs before saving.
        """
        logger.info(f'Adding new paper IDs from {len(initial_ids)} {id_type}s')
        if id_type in {'pii', 'TRID'}:
            self.paper_ids.update(set(initial_ids))
        else:
            db = get_db('primary')
            for paper_id in initial_ids:
                trids = _get_trids(db, paper_id, id_type)
                # Some papers might be not in the database yet
                if trids:
                    self.paper_ids.add(trids[0])

    def get_paper_ids_from_stmts(self, stmts):
        """Get initial set of paper IDs from a list of statements.

        Parameters
        ----------
        stmts : list[emmaa.statements.EmmaaStatement]
            A list of EMMAA statements to create the mappings from.
        """
        main_id_type = self.reading_config.get('main_id_type', 'TRID')
        logger.info(f'Extracting {main_id_type}s from statements')
        paper_ids = set()
        for estmt in stmts:
            for evid in estmt.stmt.evidence:
                if main_id_type == 'pii':
                    paper_id = evid.annotations.get('pii')
                else:
                    paper_id = evid.text_refs.get(main_id_type)
                    # In some TextRefs the keys might be lowercase
                    if not paper_id:
                        paper_id = evid.text_refs.get(main_id_type.lower())
                if paper_id:
                    paper_ids.add(paper_id)
        logger.info(f'Got {len(paper_ids)} {main_id_type}s from statements')
        return paper_ids

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
        stnames = {s.name for s in self.search_terms}
        ap = AssemblyPipeline(self.assembly_config)
        self.assembled_stmts = ap.run(stmts, stnames=stnames)

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

    def save_to_s3(self, bucket=EMMAA_BUCKET_NAME):
        """Dump the model state to S3."""
        fname = f'models/{self.name}/model_{self.date_str}'
        # Dump as pickle
        save_pickle_to_s3(self.stmts, bucket, key=fname+'.pkl')
        # Save ids to stmt hashes mapping as json
        id_fname = f'papers/{self.name}/paper_ids_{self.date_str}.json'
        save_json_to_s3(list(self.paper_ids), bucket, key=id_fname)
        # Dump as json
        # save_json_to_s3(self.to_json(), bucket, key=fname+'.json')

    @classmethod
    def load_from_s3(klass, model_name, bucket=EMMAA_BUCKET_NAME):
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
        config = load_config_from_s3(model_name, bucket=bucket)
        stmts, stmts_key = load_stmts_from_s3(model_name, bucket=bucket)
        date = strip_out_date(stmts_key)
        # Stmts and papers should be from the same date
        key = f'papers/{model_name}/paper_ids_{date}.json'
        try:
            paper_ids = load_json_from_s3(bucket, key)
        except ClientError as e:
            logger.warning(f'Could not find paper IDs mapping due to: {e}')
            paper_ids = None
        em = klass(model_name, config, paper_ids)
        em.stmts = stmts
        if not paper_ids:
            em.paper_ids = em.get_paper_ids_from_stmts(stmts)
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

    def assemble_pysb(self, mode='local', bucket=EMMAA_BUCKET_NAME):
        """Assemble the model into PySB and return the assembled model."""
        if not self.assembled_stmts:
            self.run_assembly()
        pa = PysbAssembler()
        pa.add_statements(self.assembled_stmts)
        pysb_model = pa.make_model()
        if mode == 's3':
            for exp_f in self.export_formats:
                if exp_f not in {'sbml', 'kappa', 'kappa_im', 'kappa_cm',
                                 'bngl', 'sbgn', 'pysb_flat'}:
                    continue
                fname = f'{exp_f}_{self.date_str}.{exp_f}'
                pa.export_model(exp_f, fname)
                logger.info(f'Uploading {fname}')
                client = get_s3_client(unsigned=False)
                client.upload_file(fname, bucket,
                                   f'exports/{self.name}/{fname}')
        return pysb_model

    def assemble_pybel(self, mode='local', bucket=EMMAA_BUCKET_NAME):
        """Assemble the model into PyBEL and return the assembled model."""
        if not self.assembled_stmts:
            self.run_assembly()
        pba = PybelAssembler(self.assembled_stmts)
        pybel_model = pba.make_model()
        if mode == 's3' and 'pybel' in self.export_formats:
            fname = f'pybel_{self.date_str}.bel.nodelink.json.gz'
            pybel.dump(pybel_model, fname)
            logger.info(f'Uploading {fname}')
            client = get_s3_client(unsigned=False)
            client.upload_file(fname, bucket, f'exports/{self.name}/{fname}')
        return pybel_model

    def assemble_signed_graph(self, mode='local', bucket=EMMAA_BUCKET_NAME):
        """Assemble the model into signed graph and return the assembled graph.
        """
        if not self.assembled_stmts:
            self.run_assembly()
        ia = IndraNetAssembler(self.assembled_stmts)
        signed_graph = ia.make_model(graph_type='signed')
        if mode == 's3' and 'indranet' in self.export_formats:
            fname = f'indranet_{self.date_str}.tsv'
            df = ia.make_df()
            df.to_csv(fname, sep='\t', index=False)
            logger.info(f'Uploading {fname}')
            client = get_s3_client(unsigned=False)
            client.upload_file(fname, bucket, f'exports/{self.name}/{fname}')
        return signed_graph

    def assemble_unsigned_graph(self, **kwargs):
        """Assemble the model into unsigned graph and return the assembled
        graph."""
        if not self.assembled_stmts:
            self.run_assembly()
        ia = IndraNetAssembler(self.assembled_stmts)
        unsigned_graph = ia.make_model(graph_type='digraph')
        return unsigned_graph

    def to_json(self):
        """Convert the model into a json dumpable dictionary"""
        logger.info('Converting a model to JSON')
        json_output = {'name': self.name,
                       'ndex_network': self.ndex_network,
                       'search_terms': [st.to_json() for st
                                        in self.search_terms],
                       'stmts': [st.to_json() for st in self.stmts]}
        return json_output

    def __repr__(self):
        return "EmmaModel(%s, %d stmts, %d search terms)" % \
                   (self.name, len(self.stmts), len(self.search_terms))


@register_pipeline
def filter_relevance(stmts, stnames, policy=None):
    """Filter a list of Statements to ones matching a search term."""
    logger.info('Filtering %d statements for relevance...' % len(stmts))
    stmts_out = []
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


@register_pipeline
def filter_eidos_ungrounded(stmts):
    """Filter out statements from Eidos with ungrounded agents."""
    logger.info(
        'Filtering out ungrounded Eidos statements from %d statements...'
        % len(stmts))
    stmts_out = []
    eidos_stmts = []
    for stmt in stmts:
        if stmt.evidence[0].source_api == 'eidos':
            eidos_stmts.append(stmt)
        else:
            stmts_out.append(stmt)
    eidos_grounded = filter_grounded_only(eidos_stmts)
    stmts_out += eidos_grounded
    logger.info('%d statements after filter...' % len(stmts_out))
    return stmts_out


def load_config_from_s3(model_name, bucket=EMMAA_BUCKET_NAME):
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
    base_key = f'models/{model_name}'
    config_key = f'{base_key}/config.json'
    logger.info(f'Loading model config from {config_key}')
    config = load_json_from_s3(bucket, config_key)
    return config


def save_config_to_s3(model_name, config, bucket=EMMAA_BUCKET_NAME):
    """Upload config settings for a model to S3.

    Parameters
    ----------
    model_name : str
        The name of the model whose config should be saved to S3.
    config : dict
        A JSON dict of configurations for the model.
    """
    base_key = f'models/{model_name}'
    config_key = f'{base_key}/config.json'
    logger.info(f'Saving model config to {config_key}')
    save_json_to_s3(config, bucket, config_key)


def load_stmts_from_s3(model_name, bucket=EMMAA_BUCKET_NAME):
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
    base_key = f'models/{model_name}'
    latest_model_key = find_latest_s3_file(bucket, f'{base_key}/model_',
                                           extension='.pkl')
    logger.info(f'Loading model state from {latest_model_key}')
    stmts = load_pickle_from_s3(bucket, latest_model_key)
    return stmts, latest_model_key


def _default_test(model, config=None, bucket=EMMAA_BUCKET_NAME):
    if config:
        return config['test']['default_test_corpus']
    else:
        config = load_config_from_s3(model, bucket=bucket)
        return _default_test(model, config, bucket=bucket)


def last_updated_date(model, file_type='model', date_format='date',
                      tests='large_corpus_tests', extension='.pkl', n=0,
                      bucket=EMMAA_BUCKET_NAME):
    """Find the most recent or the nth file of given type on S3 and return its
    creation date.

    Example file name:
    models/aml/model_2018-12-13-18-11-54.pkl

    Parameters
    ----------
    model : str
        Model name to look for
    file_type : str
        Type of a file to find the latest file for. Accepted values: 'model',
        'test_results', 'model_stats', 'test_stats'.
    date_format : str
        Format of the returned date. Accepted values are 'datetime' (returns a
        date in the format "YYYY-MM-DD-HH-mm-ss") and 'date' (returns a date
        in the format "YYYY-MM-DD"). Default is 'date'.
    extension : str
        The extension the model file needs to have. Default is '.pkl'
    n : int
        Index of the file in list of S3 files sorted by date (0-indexed).
    bucket : str
        Name of bucket on S3.

    Returns
    -------
    last_updated : str
        A string of the selected format.
    """
    if file_type == 'model':
        folder_name = 'models'
        prefix_new = prefix_old = f'models/{model}/model_'
    elif file_type == 'test_results':
        prefix_new = f'results/{model}/results_{tests}'
        prefix_old = f'results/{model}/results_'
    elif file_type == 'model_stats':
        prefix_new = f'model_stats/{model}/model_stats_'
        prefix_old = f'stats/{model}/stats_'
    elif file_type == 'test_stats':
        prefix_new = f'stats/{model}/test_stats_{tests}'
        prefix_old = f'stats/{model}/stats_'
    else:
        raise TypeError(f'Files of type {file_type} are not supported')
    try:
        return strip_out_date(
            find_nth_latest_s3_file(
                n=n,
                bucket=bucket,
                prefix=prefix_new,
                extension=extension),
            date_format=date_format)
    except TypeError:
        try:
            return strip_out_date(
                find_nth_latest_s3_file(
                    n=n,
                    bucket=bucket,
                    prefix=prefix_old,
                    extension=extension),
                date_format=date_format)
        except TypeError:
            logger.info('Could not find latest update date')
            return ''


def get_model_stats(model, mode, tests=None, date=None,
                    extension='.json', n=0, bucket=EMMAA_BUCKET_NAME):
    """Gets the latest statistics for the given model

    Parameters
    ----------
    model : str
        Model name to look for
    mode : str
        Type of stats to generate (model or test)
    tests : str
        A name of a test corpus. Default is large_corpus_tests.
    date : str or None
        Date for which the stats will be returned in "YYYY-MM-DD" format.
    extension : str
        Extension of the file.
    n : int
        Index of the file in list of S3 files sorted by date (0-indexed).
    bucket : str
        Name of bucket on S3.
    Returns
    -------
    model_data : json
        The json formatted data containing the statistics for the model
    """
    if not tests:
        tests = _default_test(model, bucket=bucket)
    # If date is not specified, get the latest or the nth
    if not date:
        if mode == 'model':
            date = last_updated_date(model, 'model_stats', 'date',
                                     extension=extension, n=n, bucket=bucket)
        elif mode == 'test':
            date = last_updated_date(model, 'test_stats', 'date', tests=tests,
                                     extension=extension, n=n, bucket=bucket)
        else:
            raise TypeError('Mode must be either model or tests')

    # Try find new formatted stats (separate for model and tests)
    if mode == 'model':
        # File name example:
        # model_stats/skcm/model_stats_2019-08-20-17-34-40.json
        prefix = f'model_stats/{model}/model_stats_{date}'
        latest_file_key = find_latest_s3_file(bucket=bucket,
                                              prefix=prefix,
                                              extension=extension)
    elif mode == 'test':
        # File name example:
        # stats/skcm/test_stats_large_corpus_tests_2019-08-20-17-34-40.json
        prefix = f'stats/{model}/test_stats_{tests}_{date}'
        latest_file_key = find_latest_s3_file(bucket=bucket,
                                              prefix=prefix,
                                              extension=extension)
    else:
        raise TypeError('Mode must be either model or tests')
    # This might be an older file with model and test stats combined.
    # File name example: stats/skcm/stats_2019-08-20-17-34-40.json
    if not latest_file_key and (
        mode == 'model' or (
            mode == 'test' and tests == _default_test(model))):
        prefix = f'stats/{model}/stats_{date}'
        latest_file_key = find_latest_s3_file(bucket=bucket,
                                              prefix=prefix,
                                              extension=extension)
    # If we still didn't filnd the file it probably does not exist
    if not latest_file_key:
        return None, None
    return (load_json_from_s3(bucket, latest_file_key),
            latest_file_key)


def get_assembled_statements(model, date=None, bucket=EMMAA_BUCKET_NAME):
    """Load and return a list of assembled statements.

    Parameters
    ----------
    model : str
        A name of a model.
    date : str or None
        Date in "YYYY-MM-DD" format for which to load the statements. If None,
        loads the latest available statements.
    bucket : str
        Name of S3 bucket to look for a file. Defaults to 'emmaa'.

    Returns
    -------
    stmts : list[indra.statements.Statement]
        A list of assembled statements.
    latest_file_key : str
        Key of a file with statements on s3.
    """
    if not date:
        prefix = f'assembled/{model}/statements_'
    else:
        prefix = f'assembled/{model}/statements_{date}'
    # Try loading gzip file
    latest_file_key = find_latest_s3_file(bucket, prefix, '.gz')
    if not latest_file_key:
        # Could be saved with .zip extension
        latest_file_key = find_latest_s3_file(bucket, prefix, '.zip')
    if latest_file_key:
        stmt_jsons = load_gzip_json_from_s3(bucket, latest_file_key)
    else:
        # Try loading json file
        latest_file_key = find_latest_s3_file(bucket, prefix, '.json')
        if latest_file_key:
            stmt_jsons = load_json_from_s3(bucket, latest_file_key)
        # Didn't get gzip, zip or json
        else:
            logger.info(f'No assembled statements found for {model}.')
            return None, None
    stmts = stmts_from_json(stmt_jsons)
    return stmts, latest_file_key


@register_pipeline
def load_custom_grounding_map(model, bucket=EMMAA_BUCKET_NAME):
    key = f'models/{model}/grounding_map.json'
    gr_map = load_json_from_s3(bucket, key)
    return gr_map
