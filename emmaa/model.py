import json
import time
import pickle
import logging
import datetime
from indra.databases import ndex_client
from indra.literature import pubmed_client, elsevier_client
from indra.assemblers.cx import CxAssembler
from indra.assemblers.pysb import PysbAssembler
from indra.assemblers.pybel import PybelAssembler
from indra.assemblers.indranet import IndraNetAssembler
from indra.statements import stmts_from_json
from indra.pipeline import AssemblyPipeline, register_pipeline
from indra_db.client.principal.curation import get_curations
from emmaa.priors import SearchTerm
from emmaa.readers.aws_reader import read_pmid_search_terms
from emmaa.readers.db_client_reader import read_db_pmid_search_terms
from emmaa.readers.elsevier_eidos_reader import \
    read_elsevier_eidos_search_terms
from emmaa.util import make_date_str, find_latest_s3_file, get_s3_client, \
    strip_out_date, EMMAA_BUCKET_NAME, find_nth_latest_s3_file


logger = logging.getLogger(__name__)
register_pipeline(get_curations)


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
    assembly_config : dict
        Configurations for assembling the model.
    test_config : dict
        Configurations for running tests on the model.
    reading_config : dict
        Configurations for reading the content.
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
        self.query_config = {}
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
        if 'query' in config:
            self.query_config = config['query']

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
        date_str = make_date_str()
        fname = f'models/{self.name}/model_{date_str}'
        client = get_s3_client(unsigned=False)
        # Dump as pickle
        client.put_object(Body=pickle.dumps(self.stmts),
                          Bucket=bucket,
                          Key=fname+'.pkl')
        # Dump as json
        client.put_object(Body=str.encode(json.dumps(self.to_json()),
                                          encoding='utf8'),
                          Bucket=bucket, Key=fname+'.json')

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
        stmts = load_stmts_from_s3(model_name, bucket=bucket)
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
        if not self.assembled_stmts:
            self.run_assembly()
        pa = PysbAssembler()
        pa.add_statements(self.assembled_stmts)
        pysb_model = pa.make_model()
        return pysb_model

    def assemble_pybel(self):
        """Assemble the model into PyBEL and return the assembled model."""
        if not self.assembled_stmts:
            self.run_assembly()
        pba = PybelAssembler(self.assembled_stmts)
        pybel_model = pba.make_model()
        return pybel_model

    def assemble_signed_graph(self):
        """Assemble the model into signed graph and return the assembled graph."""
        if not self.assembled_stmts:
            self.run_assembly()
        ia = IndraNetAssembler(self.assembled_stmts)
        signed_graph = ia.make_model(graph_type='signed')
        return signed_graph

    def assemble_unsigned_graph(self):
        """Assemble the model into unsigned graph and return the assembled graph."""
        if not self.assembled_stmts:
            self.run_assembly()
        ia = IndraNetAssembler(self.assembled_stmts)
        unsigned_graph = ia.make_model(graph_type='digraph')
        return unsigned_graph

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
    client = get_s3_client()
    base_key = f'models/{model_name}'
    config_key = f'{base_key}/config.json'
    logger.info(f'Loading model config from {config_key}')
    obj = client.get_object(Bucket=bucket, Key=config_key)
    config = json.loads(obj['Body'].read().decode('utf8'))
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
    client = get_s3_client(unsigned=False)
    base_key = f'models/{model_name}'
    config_key = f'{base_key}/config.json'
    logger.info(f'Saving model config to {config_key}')
    client.put_object(Body=str.encode(json.dumps(config, indent=1),
                                      encoding='utf8'),
                      Bucket=bucket, Key=config_key)


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
    client = get_s3_client()
    base_key = f'models/{model_name}'
    latest_model_key = find_latest_s3_file(bucket, f'{base_key}/model_',
                                           extension='.pkl')
    logger.info(f'Loading model state from {latest_model_key}')
    obj = client.get_object(Bucket=bucket, Key=latest_model_key)
    stmts = pickle.loads(obj['Body'].read())
    return stmts


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
    s3 = get_s3_client()

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
    model_data_object = s3.get_object(Bucket=bucket,
                                      Key=latest_file_key)
    return (json.loads(model_data_object['Body'].read().decode('utf8')),
            latest_file_key)


def get_assembled_statements(model, bucket=EMMAA_BUCKET_NAME):
    latest_file_key = find_latest_s3_file(
        bucket, f'assembled/{model}/statements_', '.json')
    if not latest_file_key:
        logger.info(f'No assembled statements found for {model}.')
        return
    client = get_s3_client()
    obj = client.get_object(Bucket=bucket, Key=latest_file_key)
    stmt_jsons = json.loads(obj['Body'].read().decode('utf8'))
    stmts = stmts_from_json(stmt_jsons)
    return stmts


@register_pipeline
def load_custom_grounding_map(model, bucket=EMMAA_BUCKET_NAME):
    key = f'models/{model}/grounding_map.json'
    client = get_s3_client()
    obj = client.get_object(Bucket=bucket, Key=key)
    gr_map = json.loads(obj['Body'].read().decode('utf-8'))
    return gr_map
