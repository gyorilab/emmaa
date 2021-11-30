import os
import json
from re import S
import boto3
import logging
import argparse
import requests
import numpy as np
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from flask import abort, Flask, request, Response, render_template, jsonify,\
    session
from flask_restx import Api, Resource, fields, inputs, abort as restx_abort
from flask_cors import CORS

from flask_jwt_extended import jwt_optional
from urllib import parse
from collections import defaultdict, Counter
from copy import deepcopy
from pusher import pusher
from sqlalchemy.sql.sqltypes import String

from indra_db.exceptions import BadHashError
from indra_db import get_db
from indra_db.util import _get_trids
from indra.statements import get_all_descendants, IncreaseAmount, \
    DecreaseAmount, Activation, Inhibition, AddModification, Agent, \
    RemoveModification, get_statement_by_name, stmts_to_json
from indra.databases import uniprot_client
from indra.ontology.standardize import standardize_name_db_refs
from indra.assemblers.html.assembler import _format_evidence_text, \
    _format_stmt_text
from indra_db.client.principal.curation import get_curations, submit_curation

from emmaa.util import find_latest_s3_file, does_exist, \
    EMMAA_BUCKET_NAME, list_s3_files, find_index_of_s3_file, \
    find_number_of_files_on_s3, FORMATTED_TYPE_NAMES
from emmaa.model import load_config_from_s3, last_updated_date, \
    get_model_stats, _default_test, get_assembled_statements
from emmaa.model_tests import load_tests_from_s3
from emmaa.answer_queries import QueryManager, load_model_manager_from_cache
from emmaa.subscription.email_util import verify_email_signature,\
    register_email_unsubscribe, get_email_subscriptions
from emmaa.queries import PathProperty, get_agent_from_text, GroundingError, \
    DynamicProperty, OpenSearchQuery, SimpleInterventionProperty
from emmaa.xdd import get_document_figures, get_figures_from_query
from emmaa.analyze_tests_results import _get_trid_title, AgentStatsGenerator
from emmaa.db import get_db as get_emmaa_db

from indralab_auth_tools.auth import auth, config_auth, resolve_auth
from indralab_web_templates.path_templates import path_temps
from indra.config import get_config
from indra.sources.hypothesis import upload_statement_annotation
from indra.databases.identifiers import get_identifiers_url


# Endpoints for EMMAA website rendering are registered with app
app = Flask(__name__)
app.register_blueprint(auth)
app.register_blueprint(path_temps)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = os.environ.get('EMMAA_SERVICE_SESSION_KEY', '')
app.config['RESTX_MASK_SWAGGER'] = False
CORS(app)

# Endpoints for programmatic access are registered with api
api = Api(app, title='EMMAA REST API', description='EMMAA REST API',
          doc='/doc')
metadata_ns = api.namespace('Metadata', 'Get EMMAA models metadata',
                            path='/metadata/')
latest_ns = api.namespace('Latest', 'Get updates specific to latest models',
                          path='/latest/')
query_ns = api.namespace('Query', 'Run EMMAA queries', path='/query/')

# Models for request body of REST API endpoints
dict_model = api.model('dict', {})
egfr = {'type': 'Agent', 'name': 'EGFR', 'db_refs': {'HGNC': '3236'}}
akt1 = {'type': 'Agent', 'name': 'AKT1', 'db_refs': {'HGNC': '391'}}
path_query_model = api.model('path_query', {
    'model': fields.String(
        example='rasmodel',
        description='A name of EMMAA model to query (e.g. aml, covid19)'),
    'source': fields.Nested(dict_model, example=egfr,
                            description='INDRA Agent JSON as a source.'),
    'target': fields.Nested(dict_model, example=akt1,
                            description='INDRA Agent JSON as a target.'),
    'stmt_type': fields.String(
        example='Activation',
        description='Type of effect between source and target.')
})
open_query_model = api.model('open_query', {
    'model': fields.String(
        example='rasmodel',
        description='A name of EMMAA model to query (e.g. aml, covid19)'),
    'entity': fields.Nested(
        dict_model, example=akt1,
        description='INDRA Agent JSON to start the search from.'),
    'entity_role': fields.String(
        example='object',
        description='subject for downstream or object for upstream search.'),
    'stmt_type': fields.String(
        example='Activation',
        description='Type of effect to search for.'),
    'terminal_ns': fields.List(
        fields.String, example=['HGNC', 'UP', 'FPLX'], required=False,
        description=('Optional list of namespaces to constrain the types of '
                     'up/downstream entities'))
})
dynamic_query_model = api.model('dynamic_query', {
    'model': fields.String(
        example='rasmodel',
        description='A name of EMMAA model to query (e.g. aml, covid19)'),
    'entity': fields.Nested(
        dict_model, example=akt1,
        description='INDRA Agent JSON for entity of interest.'),
    'pattern_type': fields.String(
        example='eventual_value', description=(
            "One of 'always_value', 'sometime_value', 'eventual_value', "
            "'no_change', 'sustained', 'transient'.")),
    'quant_value': fields.String(
        example='high', required=False, description=(
            "'high' or 'low' (only required for 'always_value', "
            "'sometime_value', 'eventual_value' pattern types)."))
})
intervention_query_model = api.model('intervention_query', {
    'model': fields.String(
        example='rasmodel',
        description='A name of EMMAA model to query (e.g. aml, covid19)'),
    'source': fields.Nested(dict_model, example=egfr,
                            description='INDRA Agent JSON as a source.'),
    'target': fields.Nested(
        dict_model, example=akt1,
        description='INDRA Agent JSON as a target. Agent can have a state.'),
    'direction': fields.String(example='up', description=(
        "'up' or 'dn' to test whether the target increased or decreased "
        "with intervention."))
})

# Parsers for query string parameters in REST API endpoints
entity_parser = api.parser()
entity_parser.add_argument('namespace', required=True,
                           help='Namespace, e.g. HGNC, CHEBI, etc.',
                           default='HGNC')
entity_parser.add_argument('id', required=True,
                           help="Entity's ID in a given namespace")

date_parser = api.parser()
date_parser.add_argument(
    'test_corpus',
    help=('Name of test corpus to find stats for, if not given default test '
          'corpus for the model will be used.'))
date_parser.add_argument(
    'date_format', help='Format of the date to return (date or datetime)')

url_parser = api.parser()
url_parser.add_argument(
    'dated', type=inputs.boolean,
    help='Whether the returned URL should be a dated version',
    default=False)

# Models for documenting responses in REST API endpoints
link_model = api.model('link', {
    'link': fields.String(example=('https://emmaa.s3.amazonaws.com/assembled/'
                                   'aml/statements_2021-05-26-17-31-41.gz'),
                          description='Link to statements file of S3')})
date_model = api.model('date', {
    'model': fields.String(example='aml', description='EMMAA model'),
    'test_corpus': fields.String(example='large_corpus_tests',
                                 description='Test corpus'),
    'date': fields.String(
        example='2021-01-01',
        description='Date of latest stats in requested format')
})
curations_model = api.model('curations', {
    'correct': fields.List(
        fields.String, example=['-32768958892027373'],
        description='Hashes of statements curated as correct'),
    'incorrect': fields.List(
        fields.String, example=['12768358492025322'],
        description='Hashes of statements curated as incorrect'),
    'partial': fields.List(
        fields.String, example=['52768978892027576'],
        description='Hashes of statements curated as having minor problems')
})
models_model = api.model('models', {
    'models': fields.List(fields.String, example=['aml', 'brca', 'covid19'])
})
model_info_model = api.model('model_info', {
    'name': fields.String(example='covid19',
                          description='Short name of EMMAA model'),
    'human_readable_name': fields.String(
        example='Covid-19', description='Human readable name of EMMAA model'),
    'description': fields.String(example=(
        'Covid-19 knowledge network automatically assembled from the '
        'CORD-19 document corpus.'),
        description='Description of a model'),
    'ndex': fields.String(example='a8c0decc-6bbb-11ea-bfdc-0ac135e8bacf',
                          description='NDEx ID of EMMAA model'),
    'twitter': fields.String(example='https://twitter.com/covid19_emmaa',
                             description='Link to model Twitter account'),
    'stmts_for_dynamic_key': fields.String(
        example='rasmachine_dynamic',
        description=(
            'A key to load statements for dynamic models, only available for '
            'models that require additional assembly steps to create a '
            'simulatable model'))
})
test_corpora_model = api.model('test_corpora', {
    'test_corpora': fields.List(
        fields.String, example=['large_corpus_tests'],
        description='List of test corpora used for this EMMAA model'
    )
})
test_info_model = api.model('test_info', {
    'name': fields.String(example='Literature-reported corpus',
                          description='Test corpus name'),
    'description': fields.String(example='Tests were curated from literature',
                                 description='Test corpus description')
})
entity_info_model = api.model('entity_info', {
    'name': fields.String(example='BRAF', description='Entity name'),
    'definition': fields.String(
        example='B-Raf proto-oncogene, serine/threonine kinase',
        description='Entity definition'),
    'url': fields.String(example='https://identifiers.org/hgnc:1097',
                         description='URL for entity'),
    'all_urls': fields.Nested(
        dict_model, description='Mapping between identifiers and URLs',
        example={"hgnc:1097": "https://identifiers.org/hgnc:1097",
                 "uniprot:P15056": "https://identifiers.org/uniprot:P15056"})
})
edge_model = api.model('edge', {
    'type': fields.String(example='statements', description='Type of edge'),
    'hashes': fields.List(fields.Integer, example=[-24400716388202410],
                          description='Hashes of statements for the edge')
})
path_model = api.model('path_result', {
    'nodes': fields.List(fields.String, example=['EGFR', 'SRC', 'AKT1'],
                         description='List of nodes in the found path'),
    'edges': fields.List(fields.Nested(edge_model, skip_none=True),
                         description='List of edges in the found path'),
    'graph_type': fields.String(
        example='signed_graph',
        description='Type of graph the path was found in'),
    'fail_reason': fields.String(
        example='Statement object state not in model',
        description='Reason why path was not found')
})
path_result_model = api.model('result', {
    'pysb': fields.Nested(path_model, skip_none=True,
                          description='Results in PySB model'),
    'pybel': fields.Nested(path_model, skip_none=True,
                           description='Results in PyBEL model'),
    'signed_graph': fields.Nested(path_model, skip_none=True,
                                  description='Results in signed graph'),
    'unsigned_graph': fields.Nested(path_model, skip_none=True,
                                    description='Results in unsigned graph'),
    'all_types': fields.String(
        example='Query is not applicable for this model', skip_none=True,
        description='If query is not applicable, only this will be returned')
})
quant_model = api.model('quantity', {
    'type': fields.String(example='qualitative',
                          description='Molecular quantity type'),
    'value': fields.String(example='low',
                           description='Molecular quantity value')
})
pattern_model = api.model('pattern', {
    'type': fields.String(example='no_change', description='Pattern type'),
    'value': fields.Nested(quant_model, skip_none=True,
                           description='Molecular quantity of an entity')
})
dynamic_fields_model = api.model('dynamic_fields', {
    'sat_rate': fields.Float(example=1.0, description='Saturation rate'),
    'num_sim': fields.Integer(example=2, description='Number of simulations'),
    'kpat': fields.Nested(pattern_model, skip_none=True,
                          description='Discovered pattern'),
    'fig_path': fields.String(
        example=('https://emmaa.s3.amazonaws.com/query_images/rasmodel/'
                 '20210527145113_AKT1_obs_2021-05-27-18-51-13.png'),
        description='Path to a resulting plot on S3'),
    'fail_reason': fields.String(
        example='Query is not applicable for this model',
        description='If query is not applicable, only this will be returned')
})
interv_fields_model = api.model('interv_fields', {
    'result': fields.String(
        example='yes_increase',
        description='Whether the target changed as expected'),
    'fig_path': fields.String(
        example=('https://emmaa.s3.amazonaws.com/query_images/rasmodel/'
                 '20210527145113_AKT1_obs_2021-05-27-18-51-13.png'),
        description='Path to a resulting plot on S3'),
    'fail_reason': fields.String(
        example='Query is not applicable for this model',
        description='If query is not applicable, only this will be returned')
})
dynamic_result_model = api.model('dynamic_result', {
    'pysb': fields.Nested(dynamic_fields_model, skip_none=True,
                          description='Results of simulating PySB model')
})
interv_result_model = api.model('interv_result', {
    'pysb': fields.Nested(interv_fields_model, skip_none=True,
                          description='Results of simulating PySB model')
})
stmt_fields = fields.Raw(example={
        "id": "acc6d47c-f622-41a4-8ae9-d7b0f3d24a2f",
        "type": "Complex",
        "members": [
            {"db_refs": {"TEXT": "MEK", "FPLX": "MEK"}, "name": "MEK"},
            {"db_refs": {"TEXT": "ERK", "FPLX": "ERK"}, "name": "ERK"}
        ],
        "sbo": "https://identifiers.org/SBO:0000526",
        "evidence": [{"text": "MEK binds ERK", "source_api": "trips"}]
        }, description='INDRA Statement JSON')

stmts_model = api.model('Statements', {
    'statements': fields.List(stmt_fields),
    'link': fields.List(fields.String, example=(
        'https://emmaa.s3.amazonaws.com/assembled/'
        'aml/statements_2021-05-26-17-31-41.gz'))
})
# Environment variables

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEVMODE = int(os.environ.get('DEVMODE', 0))
GLOBAL_PRELOAD = int(os.environ.get('GLOBAL_PRELOAD', 0))
TITLE = 'emmaa title'
ALL_MODEL_TYPES = ['pysb', 'pybel', 'signed_graph', 'unsigned_graph']
LINKAGE_SYMBOLS = {'LEFT TACK': '\u22a3',
                   'RIGHTWARDS ARROW': '\u2192'}
link_list = [('/home', 'EMMAA Dashboard'),
             ('/query?tab=static', 'Queries')]
pass_fail_msg = 'Click to see detailed results for this test'
stmt_db_link_msg = 'Click to see the evidence for this statement'
SC, jwt = config_auth(app)

ns_mapping = {'genes/proteins': ['hgnc', 'up', 'fplx'],
              'small molecules': ['chebi', 'drugbank', 'chembl', 'pubchem'],
              'biological processes': ['go', 'mesh']}
hypothesis_group = get_config('HYPOTHESIS_GROUP')

qm = QueryManager()

pusher_app_id = os.environ.get('CLARE_PUSHER_APP_ID')
pusher_key = os.environ.get('CLARE_PUSHER_KEY')
pusher_secret = os.environ.get('CLARE_PUSHER_SECRET')
pusher_cluster = os.environ.get('CLARE_PUSHER_CLUSTER')

pusher = pusher_client = pusher.Pusher(
  app_id=pusher_app_id,
  key=pusher_key,
  secret=pusher_secret,
  cluster=pusher_cluster,
  ssl=True
)


# Helper functions


def _sort_pass_fail(row):
    def _translator(status):
        if status.lower() == 'pass':
            return 0
        elif status.lower() == 'fail':
            return 1
        elif status.lower() == 'n_a':
            return 2
        else:
            raise ValueError(f'Status {status} not handled in sorting test '
                             f'table')
    # First sort on count of passing tests per row, then model type from
    # left (lower number ranks higher).
    return tuple([sum(row[n+1][1].lower() != 'pass'
                      for n in range(len(row)-1)),
                  *(_translator(row[n+1][1]) for n in range(len(row)-1))])


def is_available(model, test_corpus, date, bucket=EMMAA_BUCKET_NAME):
    if (
        does_exist(
            bucket, f'model_stats/{model}/model_stats_{date}', '.json') and
        does_exist(
            bucket, f'stats/{model}/test_stats_{test_corpus}_{date}', '.json')
    ) or (
        does_exist(bucket, f'stats/{model}/stats_{date}', '.json')
    ):
        return True
    return False


def get_latest_available_date(
        model, test_corpus, date_format='date', bucket=EMMAA_BUCKET_NAME):
    if not test_corpus:
        logger.error('Test corpus is missing, cannot find latest date')
        return
    for n in range(5):
        # First try to get last updated dates for model stats and test stats
        model_date = last_updated_date(model, 'model_stats', extension='.json',
                                       n=n, date_format=date_format,
                                       bucket=bucket)
        test_date = last_updated_date(model, 'test_stats', tests=test_corpus,
                                      extension='.json', n=n,
                                      date_format=date_format,
                                      bucket=bucket)
        if model_date == test_date:
            logger.info(f'Latest available date for {model} model and '
                        f'{test_corpus} is {model_date}.')
            return model_date
        # If last dates don't match, try to match to the earlier of them
        min_date = min(model_date, test_date)
        if is_available(model, test_corpus, min_date, bucket=bucket):
            logger.info(f'Latest available date for {model} model and '
                        f'{test_corpus} is {min_date}.')
            return min_date
    logger.info(f'Could not find latest available date for {model} model '
                f'and {test_corpus}.')


def _get_test_corpora(model, bucket=EMMAA_BUCKET_NAME):
    all_files = list_s3_files(bucket, f'stats/{model}/test_stats_', '.json')
    tests = set([os.path.basename(key)[11:-25] for key in all_files])
    return tests


def _get_available_formats(model, date, bucket=EMMAA_BUCKET_NAME):
    all_files = list_s3_files('emmaa', f'exports/{model}/')
    formats = {}
    if does_exist(bucket, f'assembled/{model}/statements_{date}', '.gz'):
        key = find_latest_s3_file(
            bucket, f'assembled/{model}/statements_{date}', '.gz')
        formats['json'] = f'https://{bucket}.s3.amazonaws.com/{key}'
    if does_exist(bucket, f'assembled/{model}/statements_{date}', '.jsonl'):
        key = find_latest_s3_file(
            bucket, f'assembled/{model}/statements_{date}', '.jsonl')
        formats['jsonl'] = f'https://{bucket}.s3.amazonaws.com/{key}'

    def get_export_format_key(key):
        base_name = key.split('/')[-1]
        exp_format = base_name.rsplit('_', maxsplit=1)[0]
        exp_format = exp_format.replace('_', ' ')
        return exp_format

    formats.update({get_export_format_key(key):
                    f'https://{bucket}.s3.amazonaws.com/{key}'
                    for key in all_files if date in key})
    return formats


def _get_all_tests(bucket=EMMAA_BUCKET_NAME):
    s3 = boto3.client('s3')
    resp = s3.list_objects(Bucket=bucket, Prefix='tests/',
                           Delimiter='_tests')
    tests = []
    for pref in resp['CommonPrefixes']:
        test = pref['Prefix'].split('/')[1]
        tests.append(test)
    return tests


def _load_tests_from_cache(test_corpus):
    tests, file_key = tests_cache.get(test_corpus, (None, None))
    try:
        latest_on_s3 = find_latest_s3_file(
            EMMAA_BUCKET_NAME, f'tests/{test_corpus}', '.pkl')
    except ValueError:
        latest_on_s3 = f'tests/{test_corpus}.pkl'
    if file_key != latest_on_s3:
        tests, file_key = load_tests_from_s3(test_corpus, EMMAA_BUCKET_NAME)
        if isinstance(tests, dict):
            tests = tests['tests']
        tests_cache[test_corpus] = (tests, file_key)
    else:
        logger.info(f'Loaded {test_corpus} from cache.')
    return tests


def _load_stmts_from_cache(model, date):
    # Only store stmts for one date for browsing on one page, if needed load
    # statements for different date
    available_date, stmts = stmts_cache.get(model, (None, None))
    if date and available_date == date:
        logger.info(f'Loaded assembled stmts for {model} {date} from cache.')
        return stmts
    stmts, file_key = get_assembled_statements(model, date, EMMAA_BUCKET_NAME)
    stmts_cache[model] = (date, stmts)
    return stmts


def load_stmts(model, date, **kwargs):
    emmaa_db = get_emmaa_db('dev')
    stmts = emmaa_db.get_statements(model, date, **kwargs)
    from_db = True
    # Statements for that model/date are not in db
    if not stmts:
        logger.info(f'Could not find statements for {model} {date} in db, '
                    'using S3/cache.')
        stmts = _load_stmts_from_cache(model, date)
        from_db = False
    return stmts, from_db


def load_stmts_by_hash(model, date, stmt_hashes):
    emmaa_db = get_emmaa_db('dev')
    stmts = emmaa_db.get_statements_by_hash(model, date, stmt_hashes)
    # Statements for that model/date are not in db
    if not stmts:
        stmts = _load_stmts_from_cache(model, date)
        stmts = [stmt for stmt in stmts if str(stmt.get_hash()) in stmt_hashes]
    return stmts


def load_path_counts(model, date):
    emmaa_db = get_emmaa_db('dev')
    return emmaa_db.get_path_counts(model, date)


def _load_model_stats_from_cache(model, date):
    available_date, model_stats = model_stats_cache.get(model, (None, None))
    if model_stats and date and available_date == date:
        logger.info(f'Loaded model stats for {model} {date} from cache')
        return model_stats
    model_stats, _ = get_model_stats(model, 'model', date=date)
    model_stats_cache[model] = (date, model_stats)
    return model_stats


def _load_test_stats_from_cache(model, test_corpus, date=None):
    available_date, test_stats, file_key = test_stats_cache.get(
        (model, test_corpus), (None, None, None))
    if test_stats and date and available_date == date:
        logger.info(f'Loaded test stats for {model} and {test_corpus} {date}'
                    ' from cache')
        return test_stats, file_key
    test_stats, file_key = get_model_stats(model, 'test', tests=test_corpus,
                                           date=date)
    test_stats_cache[(model, test_corpus)] = (date, test_stats, file_key)
    return test_stats, file_key


def _get_model_meta_data(bucket=EMMAA_BUCKET_NAME):
    s3 = boto3.client('s3')
    resp = s3.list_objects(Bucket=bucket, Prefix='models/',
                           Delimiter='/')
    model_data = []
    for pref in resp['CommonPrefixes']:
        model = pref['Prefix'].split('/')[1]
        config_json = get_model_config(model, bucket=bucket)
        if not config_json:
            continue
        dev_only = config_json.get('dev_only', False)
        if dev_only:
            if DEVMODE:
                model_data.append((model, config_json))
            else:
                continue
        else:
            model_data.append((model, config_json))
    return model_data


def get_model_config(model, bucket=EMMAA_BUCKET_NAME):
    if model in model_cache:
        return model_cache[model]
    try:
        config_json = load_config_from_s3(model, bucket=bucket)
        model_cache[model] = config_json
    except ClientError:
        logger.warning(f"Model {model} has no metadata. Skipping...")
        return None
    if 'human_readable_name' not in config_json.keys():
        logger.warning(f"Model {model} has no readable name. Skipping...")
        model_cache[model] = None
    return model_cache[model]


model_cache = {}
tests_cache = {}
stmts_cache = {}
model_stats_cache = {}
test_stats_cache = {}
if GLOBAL_PRELOAD:
    # Load all the model configs
    model_meta_data = _get_model_meta_data()
    # Load all the model managers for queries
    for model, _ in model_meta_data:
        load_model_manager_from_cache(model)
    tests = _get_all_tests()
    for test_corpus in tests:
        _load_tests_from_cache(test_corpus)


def get_queryable_stmt_types():
    """Return Statement class names that can be used for querying."""
    def get_sorted_descendants(cls):
        return sorted(get_names(get_all_descendants(cls)))

    def get_names(classes):
        return [s.__name__ for s in classes]

    stmt_types = \
        get_names([Activation, Inhibition, IncreaseAmount, DecreaseAmount]) + \
        get_sorted_descendants(AddModification) + \
        get_sorted_descendants(RemoveModification)
    return stmt_types


def _make_query(query_dict):
    query_type = query_dict['queryType']
    if query_type in ['static', 'intervention']:
        stmt_type = query_dict['typeSelection']
        stmt_class = get_statement_by_name(stmt_type)
        subj = get_agent_from_text(
            query_dict['subjectSelection'])
        obj = get_agent_from_text(
            query_dict['objectSelection'])
        stmt = stmt_class(subj, obj)
        if query_type == 'static':
            query = PathProperty(path_stmt=stmt)
        elif query_type == 'intervention':
            query = SimpleInterventionProperty.from_stmt(stmt)
    elif query_type == 'dynamic':
        agent = get_agent_from_text(query_dict['agentSelection'])
        value = query_dict['valueSelection']
        if not value:
            value = None
        pattern = query_dict['patternSelection']
        query = DynamicProperty(agent, pattern, value)
    elif query_type == 'open':
        agent = get_agent_from_text(query_dict['openAgentSelection'])
        stmt_type = query_dict['stmtTypeSelection']
        role = query_dict['roleSelection']
        ns_groups = query_dict['nsSelection']
        if not ns_groups:
            terminal_ns = None
        else:
            terminal_ns = []
            for gr in ns_groups:
                terminal_ns += ns_mapping[gr]
        query = OpenSearchQuery(agent, stmt_type, role, terminal_ns)
    return query, query_type


def _new_applied_tests(test_stats_json, model_types, model_name, date,
                       test_corpus, add_links=False):
    # Extract new applied tests into:
    #   list of tests (one per row)
    #       each test is a list of tuples (one tuple per column)
    #           each tuple is a (href, link_text) pair
    all_test_results = test_stats_json['test_round_summary'][
        'all_test_results']
    new_app_hashes = test_stats_json['tests_delta']['applied_hashes_delta'][
        'added']
    if len(new_app_hashes) == 0:
        return 'No new tests were applied'
    new_app_tests = [(th, all_test_results[th]) for th in new_app_hashes]
    return _format_table_array(new_app_tests, model_types, model_name, date,
                               test_corpus, add_links=add_links)


def _format_table_array(tests_json, model_types, model_name, date,
                        test_corpus, add_links=False):
    # tests_json needs to have the structure: [(test_hash, tests)]
    table_array = []
    for th, test in tests_json:
        if add_links:
            ev_url_par = parse.urlencode(
                {'stmt_hash': th, 'source': 'test', 'model': model_name,
                 'test_corpus': test_corpus, 'date': date})
            test['test'][0] = f'/evidence?{ev_url_par}'
            test['test'][2] = stmt_db_link_msg
        new_row = [(test['test'])]
        for mt in model_types:
            url_param = parse.urlencode(
                {'model_type': mt, 'test_hash': th, 'date': date,
                 'test_corpus': test_corpus})
            new_row.append((f'/tests/{model_name}?{url_param}',
                            test[mt][0], pass_fail_msg))
        table_array.append(new_row)
    return sorted(table_array, key=_sort_pass_fail)


def _format_query_results(formatted_results):
    result_array = []
    for qh, res in formatted_results.items():
        model_types = [mt for mt in ALL_MODEL_TYPES if mt in res]
        model = res['model']
        latest_date = get_latest_available_date(
            model, _default_test(model))
        new_res = [('', res["query"], ''),
                   (f'/dashboard/{model}?date={latest_date}' +
                    f'&test_corpus={_default_test(model)}&tab=model',
                    model,
                    f'Click to see details about {model}')]
        for mt in model_types:
            url_param = parse.urlencode(
                {'model_type': mt, 'query_hash': qh, 'order': 1})
            new_res.append((f'/query/{model}?{url_param}', res[mt][0],
                            'Click to see detailed results for this query'))
        result_array.append(new_res)
    return result_array


def _format_dynamic_query_results(formatted_results):
    result_array = []
    for qh, res in formatted_results.items():
        model = res['model']
        new_res = [('', res['query'], ''),
                   ('', model, ''),
                   ('', res['result'][0], res['result'][1])]
        if res.get('image'):
            new_res.append((res['image'], '', ''))
        else:
            new_res.append(('', 'n_a', ''))
        result_array.append(new_res)
    return result_array


def _get_mt_rows(model_name, mt, msg, hashes, all_test_results, date,
                 test_corpus, add_links):
    mt_rows = [[('', f'{msg} {FORMATTED_TYPE_NAMES[mt]} model.', '')]]
    for th in hashes:
        test = all_test_results[th]
        if add_links:
            ev_url_par = parse.urlencode(
                {'stmt_hash': th, 'source': 'test', 'model': model_name,
                    'test_corpus': test_corpus, 'date': date})
            test['test'][0] = f'/evidence?{ev_url_par}'
            test['test'][2] = stmt_db_link_msg
        path_loc = test[mt][1]
        if isinstance(path_loc, list):
            path = path_loc[0]['path']
        else:
            path = path_loc
        url_param = parse.urlencode(
            {'model_type': mt, 'test_hash': th, 'date': date,
                'test_corpus': test_corpus})
        new_row = [(test['test']),
                   (f'/tests/{model_name}?{url_param}', path,
                    pass_fail_msg)]
        mt_rows.append(new_row)
    return mt_rows


def _new_passed_tests(model_name, test_stats_json, current_model_types, date,
                      test_corpus, add_links=False):
    new_passed_tests = []
    all_test_results = test_stats_json['test_round_summary'][
        'all_test_results']
    for mt in current_model_types:
        new_passed_hashes = test_stats_json['tests_delta'][mt][
            'passed_hashes_delta']['added']
        if not new_passed_hashes:
            continue
        mt_rows = _get_mt_rows(
            model_name, mt, 'New passed tests for', new_passed_hashes,
            all_test_results, date, test_corpus, add_links)
        new_passed_tests += mt_rows
    if len(new_passed_tests) > 0:
        return new_passed_tests
    return 'No new tests were passed'


def _agent_paths_tests(model_name, agent_paths, test_stats_json, date,
                       current_model_types, test_corpus, add_links=False):
    agent_path_tests = []
    all_test_results = test_stats_json['test_round_summary'][
        'all_test_results']
    for mt in current_model_types:
        mt_path_hashes = agent_paths.get(mt)
        if not mt_path_hashes:
            continue
        mt_rows = _get_mt_rows(
            model_name, mt, 'Paths in', mt_path_hashes,
            all_test_results, date, test_corpus, add_links)
        agent_path_tests += mt_rows
    if len(agent_path_tests) > 0:
        return agent_path_tests
    return 'No paths with this agent'


def _set_curation(stmt_hash, correct, incorrect):
    cur = ''
    if isinstance(stmt_hash, list):
        if set(stmt_hash).intersection(correct):
            cur = 'correct'
        elif set(stmt_hash).intersection(incorrect):
            cur = 'incorrect'
    else:
        if stmt_hash in correct:
            cur = 'correct'
        if stmt_hash in incorrect:
            cur = 'incorrect'
    return cur


def _label_curations(include_partial=False, **kwargs):
    logger.info('Getting curations')
    curations = get_curations(**kwargs)
    logger.info('Labeling curations')
    if include_partial:
        correct = {str(c['pa_hash']) for c in curations if
                   c['tag'] == 'correct'}
        partial = {str(c['pa_hash']) for c in curations if
                   c['tag'] in ['act_vs_amt', 'hypothesis'] and
                   str(c['pa_hash']) not in correct}
        incorrect = {str(c['pa_hash']) for c in curations if
                     str(c['pa_hash']) not in correct and
                     str(c['pa_hash']) not in partial}
        return correct, incorrect, partial
    correct_tags = ['correct', 'act_vs_amt', 'hypothesis']
    correct = {str(c['pa_hash']) for c in curations if
               c['tag'] in correct_tags}
    incorrect = {str(c['pa_hash']) for c in curations if
                 str(c['pa_hash']) not in correct}
    logger.info('Labeled curations as correct or incorrect')
    return correct, incorrect


def _count_curations(curations, stmts_by_hash):
    correct_tags = ['correct', 'act_vs_amt', 'hypothesis']
    cur_counts = {}
    for cur in curations:
        stmt_hash = str(cur['pa_hash'])
        if stmt_hash not in stmts_by_hash:
            continue
        if stmt_hash not in cur_counts:
            cur_counts[stmt_hash] = {
                'this': defaultdict(int),
                'other': defaultdict(int),
            }
        if cur['tag'] in correct_tags:
            cur_tag = 'correct'
        else:
            cur_tag = 'incorrect'
        if cur['source_hash'] in [evid.get_source_hash() for evid in
                                  stmts_by_hash[stmt_hash].evidence]:
            cur_source = 'this'
        else:
            cur_source = 'other'
        cur_counts[stmt_hash][cur_source][cur_tag] += 1
    return cur_counts


def _local_sort_stmts(stmts, stmts_by_hash, offset, sort_by):
    # This is the old way of sorting statements after loading all of them
    # in memory, used when statements are not available in the db
    stmt_counts_dict = Counter()
    test_corpora = _get_test_corpora(model)
    for test_corpus in test_corpora:
        test_date = last_updated_date(model, 'test_stats', 'date', test_corpus,
                                      extension='.json')
        test_stats, _ = _load_test_stats_from_cache(
            model, test_corpus, test_date)
        stmt_counts = test_stats['test_round_summary'].get(
            'path_stmt_counts', [])
        stmt_counts_dict += Counter(dict(stmt_counts))
    if sort_by == 'evidence':
        stmts = sorted(stmts, key=lambda x: len(x.evidence), reverse=True)[
            offset:offset+1000]
    elif sort_by == 'paths':
        stmt_count_sorted = sorted(
            stmt_counts_dict.items(), key=lambda x: x[1], reverse=True)
        if not stmt_count_sorted:
            msg = 'Sorting by paths is not available, sorting by evidence'
            stmts = sorted(stmts, key=lambda x: len(x.evidence), reverse=True)[
                offset:offset+1000]
        else:
            stmts = []
            for (stmt_hash, count) in stmt_count_sorted[offset:offset+1000]:
                try:
                    stmts.append(stmts_by_hash[stmt_hash])
                except KeyError:
                    continue
    elif sort_by == 'belief':
        stmts = sorted(stmts, key=lambda x: x.belief, reverse=True)[
            offset:offset+1000]
    return stmts, stmt_counts_dict


def _get_stmt_row(stmt, source, model, cur_counts, date, test_corpus=None,
                  path_counts=None, cur_dict=None, with_evid=False,
                  paper_id=None, paper_id_type=None):
    stmt_hash = str(stmt.get_hash(refresh=True))
    english = _format_stmt_text(stmt)
    evid_count = len(stmt.evidence)
    evid = []
    if with_evid and cur_dict is not None:
        evid = json.loads(json.dumps(_format_evidence_text(
            stmt, cur_dict, ['correct', 'act_vs_amt', 'hypothesis'])))[:10]
    params = {'stmt_hash': stmt_hash, 'source': source, 'model': model,
              'format': 'json', 'date': date}
    if test_corpus:
        params.update({'test_corpus': test_corpus})
    if source == 'paper' and paper_id:
        params.update({'paper_id': paper_id})
        if paper_id_type:
            params.update({'paper_id_type': paper_id_type})
    url_param = parse.urlencode(params)
    json_link = f'/evidence?{url_param}'
    path_count = 0
    if path_counts:
        path_count = path_counts.get(stmt_hash)
    neg = len([ev for ev in stmt.evidence if ev.epistemics.get('negated')])
    badges = _make_badges(evid_count, json_link, path_count,
                          round(stmt.belief, 2),
                          cur_counts.get(stmt_hash), neg)
    stmt_row = [
        (stmt.get_hash(refresh=True), english, evid, evid_count, badges)]
    return stmt_row


def _make_badges(evid_count, json_link, path_count, belief, cur_counts=None,
                 neg=None):
    badges = [
        {'label': 'stmt_json', 'num': 'JSON', 'color': '#b3b3ff',
         'symbol': None, 'title': 'View statement JSON', 'href': json_link,
         'loc': 'right'},
        {'label': 'evidence', 'num': evid_count, 'color': 'grey',
         'symbol': None, 'title': 'Evidence count for this statement',
         'loc': 'right'},
        {'label': 'paths', 'num': path_count, 'symbol': '\u2691',
         'color': '#0099ff', 'title': 'Number of paths with this statement'},
        {'label': 'belief', 'num': belief, 'color': '#ffc266',
         'symbol': None, 'title': 'Belief score for this statement',
         'loc': 'right'}]
    if cur_counts:
        badges += [
            {'label': 'correct_this', 'num': cur_counts['this']['correct'],
             'color': '#28a745', 'symbol':  '\u270E',
             'title': 'Curated as correct in this model'},
            {'label': 'incorrect_this', 'num': cur_counts['this']['incorrect'],
             'color': '#ff8080', 'symbol': '\u270E',
             'title': 'Curated as incorrect in this model'},
            {'label': 'correct_other', 'num': cur_counts['other']['correct'],
             'color': '#adebbb', 'symbol': '\u270E',
             'title': 'Curated as correct outside of this model'},
            {'label': 'incorrect_other', 'symbol': '\u270E',
             'num': cur_counts['other']['incorrect'], 'color': '#ffcccc',
             'title': 'Curated as incorrect outside of this model'}]
    if neg:
        badges.append(
            {'label': 'negative', 'num': neg,
             'color': '#ffb3b3', 'symbol':  '\uFF0D ',
             'title': f'Has {neg} negative evidence'}
        )
    return badges


def get_new_papers(model, model_stats, date):
    paper_id_counts = []
    trids = model_stats['paper_delta']['raw_paper_ids_delta']['added']
    for paper_id in trids:
        assembled_count = len(model_stats['paper_summary'][
            'stmts_by_paper'].get(str(paper_id), []))
        raw_count = model_stats['paper_summary']['raw_paper_counts'].get(
            str(paper_id), 0)
        paper_id_counts.append((paper_id, assembled_count, raw_count))
    paper_id_counts = sorted(paper_id_counts, key=lambda x: (x[1], x[2]),
                             reverse=True)
    if not paper_id_counts:
        return 'Did not process new papers'
    new_papers = [[_get_paper_title_tuple(paper_id, model_stats, date),
                   _get_external_paper_link(model, paper_id, model_stats),
                   ('', str(assembled_count), ''),
                   ('', str(raw_count), '')]
                  for paper_id, assembled_count, raw_count in paper_id_counts]
    return new_papers


def _get_title(paper_id, model_stats):
    id_to_title = model_stats['paper_summary'].get('paper_titles')
    title = None
    if id_to_title:
        title = id_to_title.get(str(paper_id))
    if title is None:
        title = _get_trid_title(paper_id)
    if title:
        return title
    return "Title not available"


def _get_paper_title_tuple(paper_id, model_stats, date):
    title = _get_title(paper_id, model_stats)
    stmts_by_paper_id = model_stats['paper_summary']['stmts_by_paper']
    stmt_hashes = [
        str(st_hash) for st_hash in stmts_by_paper_id.get(str(paper_id), [])]
    model = model_stats['model_summary']['model_name']
    url_param = parse.urlencode(
        {'paper_id': paper_id, 'paper_id_type': 'trid', 'date': date})
    url = f'/statements_from_paper/{model}?{url_param}'
    paper_tuple = (url, title, 'Click to see statements from this paper')
    return paper_tuple


def _get_external_paper_link(model, paper_id, model_stats):
    trid_to_link = model_stats['paper_summary'].get('paper_links', {})
    paper_hashes = model_stats['paper_summary']['stmts_by_paper'].get(
        str(paper_id))
    if trid_to_link.get(str(paper_id)):
        link, name = trid_to_link[str(paper_id)]
        if paper_hashes:
            url_param = parse.urlencode(
                {'paper_id': paper_id, 'paper_id_type': 'trid'})
            ann_url = f'/annotate_paper/{model}?{url_param}'
            paper_tuple = ('annotate', ann_url, paper_id, link, name,
                           'Click to view this paper')
        else:
            paper_tuple = (link, name, 'Click to view this paper')
    else:
        paper_tuple = ('', 'N/A', '')
    return paper_tuple


def filter_evidence(stmt, paper_id, paper_id_type):
    stmt2 = deepcopy(stmt)
    stmt2.evidence = []
    for evid in stmt.evidence:
        evid_paper_id = None
        if paper_id_type == 'pii':
            evid_paper_id = evid.annotations.get('pii')
        if evid.text_refs:
            evid_paper_id = evid.text_refs.get(paper_id_type.upper())
            if not evid_paper_id:
                evid_paper_id = evid.text_refs.get(paper_id_type.lower())
        if evid_paper_id and str(evid_paper_id) == str(paper_id):
            stmt2.evidence.append(evid)
    return stmt2


def get_immediate_queries(query_type):
    headers = None
    results = 'Results for submitted queries'
    if session.get('query_hashes') and session['query_hashes'].get(query_type):
        query_hashes = session['query_hashes'][query_type]
        qr = qm.retrieve_results_from_hashes(query_hashes, query_type)
        if query_type in ['path_property', 'open_search_query']:
            headers = ['Query', 'Model'] + [
                FORMATTED_TYPE_NAMES[mt] for mt in ALL_MODEL_TYPES if mt in
                list(qr.values())[0]] if qr else []
            results = _format_query_results(qr) if qr else\
                'No stashed results for subscribed queries. Please re-run ' \
                'query to see latest result.'
        elif query_type in ['dynamic_property',
                            'simple_intervention_property']:
            headers = ['Query', 'Model', 'Result', 'Image']
            results = _format_dynamic_query_results(qr)
    return results, headers


def get_subscribed_queries(query_type, user_email=None):
    headers = []
    if user_email:
        res = qm.get_registered_queries(user_email, query_type)
        if res:
            if query_type in ['path_property', 'open_search_query']:
                sub_results = _format_query_results(res)
                headers = ['Query', 'Model'] + [
                    FORMATTED_TYPE_NAMES[mt] for mt in ALL_MODEL_TYPES]
            elif query_type in ['dynamic_property',
                                'simple_intervention_property']:
                sub_results = _format_dynamic_query_results(res)
                headers = ['Query', 'Model', 'Result', 'Image']
        else:
            sub_results = 'You have no subscribed queries'
    else:
        sub_results = 'Please log in to see your subscribed queries'
    return sub_results, headers


def _update_bioresolver(prefix: str, identifier: str, rv) -> None:
    bioresolver_json = _lookup_bioresolver(prefix, identifier)
    if not bioresolver_json:
        return
    for key in 'name', 'definition', 'species':
        if not rv.get(key):
            rv[key] = bioresolver_json.get(key)


def _lookup_bioresolver(prefix: str, identifier: str):
    url = get_config('ENTITY_RESOLVER_URL')
    if url is None:
        return
    try:
        res = requests.get(f'{url}/api/lookup/{prefix}:{identifier}')
        res_json = res.json()
        if not res_json['success']:
            return  # there was a problem looking up CURIE in the Biolookup Service
    except Exception as e:
        logger.warning(e)
        logger.warning('Could not connect to the Biolookup Service')
        return
    return res_json


def get_entity_info(namespace, identifier):
    std_name, db_refs = standardize_name_db_refs({namespace: identifier})
    up_id = db_refs.get('UP')
    original_url = get_identifiers_url(namespace, identifier)
    urls = [get_identifiers_url(k, v) for k, v in db_refs.items()]
    all_urls = {url.split('/')[-1]: url for url in urls if url}
    rv = {'url': original_url, 'all_urls': all_urls, 'name': std_name}
    if up_id:
        rv['definition'] = uniprot_client.get_function(up_id)
    else:
        rv['definition'] = None
    _update_bioresolver(namespace, identifier, rv)
    return rv


def _run_query(query, model):
    mm = load_model_manager_from_cache(model)
    full_results = mm.answer_query(query)
    results = {}
    for mc_type, _, paths in full_results:
        if mc_type:
            results[mc_type] = paths
        else:
            results['all_types'] = paths
    return results


# Dashboard endpoints

# Deletes session after the specified time
@app.before_request
def session_expiration_check():
    session.permanent = True
    session.modified = True
    app.permanent_session_lifetime = timedelta(minutes=10)


@app.route('/health')
@jwt_optional
def health():
    return jsonify({'status': 'pass'})


@app.route('/')
@app.route('/home')
@jwt_optional
def get_home():
    loaded = request.args.get('loaded')
    loaded = (loaded == 'true')
    if not loaded:
        return render_template(
            'loading.html',
            msg='Please wait while we load the models...')
    user, roles = resolve_auth(dict(request.args))
    model_data = _get_model_meta_data()
    return render_template('index_template.html', model_data=model_data,
                           link_list=link_list,
                           user_email=user.email if user else "")


@app.route('/dashboard/<model>')
@jwt_optional
def get_model_dashboard(model):
    """Render model dashboard page."""
    loaded = request.args.get('loaded')
    loaded = (loaded == 'true')
    agent = request.args.get('agent')
    if not loaded:
        if agent:
            return render_template(
                'loading.html',
                msg=('Please wait while we generate the '
                     'statistics about this agent...'))
        else:
            return render_template(
                'loading.html',
                msg='Please wait while we load the model statistics...')
    test_corpus = request.args.get('test_corpus', _default_test(
        model, get_model_config(model)))
    if not test_corpus:
        abort(Response('Could not identify test corpus', 404))
    date = request.args.get('date')
    latest_date = get_latest_available_date(
        model, test_corpus)
    if not date:
        date = latest_date
    tab = request.args.get('tab', 'model')
    user, roles = resolve_auth(dict(request.args))
    logger.info(f'Loading {tab} dashboard for {model} and {test_corpus} '
                f'at {date}.')
    model_meta_data = _get_model_meta_data()
    model_stats = _load_model_stats_from_cache(model, date)
    test_stats, _ = _load_test_stats_from_cache(model, test_corpus, date)
    if not model_stats or not test_stats:
        abort(Response(f'Data for {model} and {test_corpus} for {date} '
                       f'was not found', 404))

    exp_formats = _get_available_formats(model, date, EMMAA_BUCKET_NAME)
    logger.info('Getting model information')
    ndex_id = None
    description = 'None available'
    for mid, mmd in model_meta_data:
        if mid == model:
            try:
                ndex_id = mmd['ndex']['network']
            except KeyError:
                pass
            description = mmd['description']
            twitter_link = mmd.get('twitter_link')
            exports = mmd.get('export_formats', [])
            kappa_ui = 'kappa_ui' in exports
    if ndex_id is None:
        logger.warning(f'No ndex ID found for {model}')
    available_tests = _get_test_corpora(model)
    model_info_contents = [
        [('', 'Model Description', ''), ('', description, '')],
        [('', 'Latest Data Available', ''), ('', latest_date, '')],
        [('', 'Data Displayed', ''),
         ('', date,
          'Click on the point on time graph to see earlier results')]]
    if ndex_id:
        model_info_contents.append([
         ('', 'Network on Ndex', ''),
         (f'http://www.ndexbio.org/#/network/{ndex_id}', ndex_id,
          'Click to see network on Ndex')])
    if twitter_link:
        model_info_contents.append([
            ('', 'Twitter', ''),
            (twitter_link, ''.join(['@', twitter_link.split('/')[-1]]),
             "Click to see model's Twitter page")])
    if kappa_ui and 'kappa' in exp_formats:
        kappa_link = ('https://tools.kappalanguage.org/try/?'
                      f'model={exp_formats["kappa"]}')
        model_info_contents.append([
            ('', 'Kappa UI', ''),
            (kappa_link, 'Kappa UI', 'Explore model on Kappa UI')])
    logger.info('Getting model subscription info')
    subscribe = True
    logged_in = False
    sub_link = f'/subscribe/{model}'
    if user:
        logged_in = True
        model_users = qm.db.get_model_users(model)
        if user.email in model_users:
            subscribe = False
    subscription = (logged_in, subscribe, sub_link)
    logger.info('Getting test information')
    test_data = test_stats['test_round_summary'].get('test_data')
    test_info_contents = None
    if test_data:
        test_info_contents = [[('', ' '.join(k.split('_')).capitalize(), ''),
                               ('', v, '')] for k, v in test_data.items()]
    else:
        test_stats['test_round_summary']['test_data'] = ''
    current_model_types = [mt for mt in ALL_MODEL_TYPES if mt in
                           test_stats['test_round_summary']]
    # Get correct and incorrect curation hashes to pass it per stmt
    correct, incorrect = _label_curations()
    logger.info('Mapping curations to tests')
    # Filter out rows with all tests == 'n_a'
    all_tests = []
    for k, v in test_stats['test_round_summary']['all_test_results'].items():
        if all(v[mt][0].lower() == 'n_a' for mt in current_model_types):
            continue
        else:
            cur = _set_curation(k, correct, incorrect)
            val = deepcopy(v)
            val['test'].append(cur)
            all_tests.append((k, val))
    # Add links unless sure they are added in stats
    add_test_links = test_stats.get('add_links', True)

    def _update_stmt(st_hash, st_value, add_links=False):
        if add_links:
            url_param = parse.urlencode(
                {'stmt_hash': st_hash, 'source': 'model_statement',
                 'model': model, 'date': date})
            st_value[0] = f'/evidence?{url_param}'
            st_value[2] = stmt_db_link_msg
        cur = _set_curation(st_hash, correct, incorrect)
        st_value.append(cur)
        return (st_value)

    all_stmts = model_stats['model_summary']['all_stmts']
    # Add links unless sure they are added in stats
    add_model_links = model_stats.get('add_links', True)

    most_supported = model_stats['model_summary']['stmts_by_evidence'][:10]
    added_stmts_hashes = \
        model_stats['model_delta']['statements_hashes_delta']['added']
    top_stmts_counts = []
    logger.info('Mapping curations to most supported statements')
    for st_hash, c in most_supported:
        st_value = deepcopy(all_stmts[st_hash])
        top_stmts_counts.append(
            ((_update_stmt(st_hash, st_value, add_model_links)),
             ('', str(c), '')))

    if len(added_stmts_hashes) > 0:
        logger.info('Mapping curations to new added statements')
        added_stmts = []
        for st_hash in added_stmts_hashes:
            st_value = deepcopy(all_stmts[st_hash])
            added_stmts.append(
                (_update_stmt(st_hash, st_value, add_model_links),))
    else:
        added_stmts = 'No new statements were added'

    logger.info('Getting paper statistics')
    if not model_stats['paper_summary'].get('paper_titles'):
        paper_distr = 'Paper titles are not currently available'
        new_papers = 'Paper titles are not currently available'
    else:
        trids_counts = model_stats['paper_summary']['paper_distr'][:10]
        paper_distr = [[_get_paper_title_tuple(paper_id, model_stats, date),
                        _get_external_paper_link(model, paper_id, model_stats),
                        ('', str(c), '')] for paper_id, c in trids_counts]
        new_papers = get_new_papers(model, model_stats, date)

    logger.info('Getting belief distribution')
    belief_data = {}
    beliefs = model_stats['model_summary'].get('assembled_beliefs')
    stmts = None
    if not beliefs:
        stmts, _ = load_stmts(model, date)
        if stmts:
            beliefs = [stmt.belief for stmt in stmts]
    if beliefs:
        belief_freq, x = np.histogram(beliefs, 'doane')
        belief_x = [round(n, 2) for n in x]
        # Sometimes the bins are too close and rounding gets identical numbers
        if len(belief_x) != len(set(belief_x)):
            belief_x = [round(n, 3) for n in x]
        belief_freq = ['Beliefs'] + list(belief_freq) + [0]
        belief_data = {'x': belief_x, 'freq': belief_freq}

    all_agents = [ag for (ag, count) in
                  model_stats['model_summary']['agent_distr']]
    agent_stats = {}
    agent_info = None
    agent_stmts_counts = None
    agent_added_stmts = None
    agent_paper_distr = None
    agent_tests_table = None
    agent_paths_table = None
    if agent:
        logger.info('Generating agent statistics')
        if not stmts:
            stmts, _ = load_stmts(model, date)
        sg = AgentStatsGenerator(model, agent, stmts, model_stats, test_stats)
        sg.make_stats()
        agent_stats = sg.json_stats
        agent_refs = agent_stats['agent_summary']
        agent_dict = get_entity_info(agent_refs['namespace'], agent_refs['id'])
        agent_info = []
        for k in ['name', 'definition', 'species']:
            if agent_dict.get(k):
                agent_info.append(
                    [('', k.capitalize(), ''), ('', agent_dict[k], '')])
        for ns_id, url in agent_dict['all_urls'].items():
            agent_info.append(
                [('', ns_id.upper(), ''), (url, url, 'Click to view more')])
        agent_supported = agent_stats['model_summary'][
            'stmts_by_evidence'][:10]
        agent_added_hashes = \
            agent_stats['model_delta']['statements_hashes_delta']['added']
        if len(agent_supported) > 0:
            agent_stmts_counts = []
            logger.info('Mapping curations to agent most supported statements')
            for st_hash, c in agent_supported:
                st_value = deepcopy(all_stmts[st_hash])
                agent_stmts_counts.append(
                    ((_update_stmt(st_hash, st_value, add_model_links)),
                     ('', str(c), '')))
        else:
            agent_stmts_counts = f'No statements with {agent} were found'
        if len(agent_added_hashes) > 0:
            logger.info('Mapping curations to new added statements with agent')
            agent_added_stmts = []
            for st_hash in agent_added_hashes:
                st_value = deepcopy(all_stmts[st_hash])
                agent_added_stmts.append(
                    (_update_stmt(st_hash, st_value, add_model_links),))
        else:
            agent_added_stmts = f'No new statements with {agent} were added'
        logger.info('Getting agent test statistics')
        agent_tests = [(th, test) for (th, test) in all_tests if th in
                       agent_stats['test_round_summary']['agent_tests']]
        if agent_tests:
            agent_tests_table = _format_table_array(
                agent_tests, current_model_types, model, date,
                test_corpus, add_test_links)
        else:
            agent_tests_table = 'No tests with this agent'
        agent_paths = agent_stats['test_round_summary']['agent_paths']
        agent_paths_table = _agent_paths_tests(
            model, agent_paths, test_stats, date, current_model_types,
            test_corpus, add_test_links)
        logger.info('Getting agent paper statistics')
        agent_trids_counts = agent_stats['paper_summary']['paper_distr'][:10]
        if len(agent_trids_counts) > 0:
            agent_paper_distr = [
                [_get_paper_title_tuple(paper_id, agent_stats, date),
                 _get_external_paper_link(model, paper_id, agent_stats),
                 ('', str(c), '')] for paper_id, c in agent_trids_counts]
        else:
            agent_paper_distr = f'No papers about {agent} were found'
    logger.info('Rendering page')
    return render_template('model_template.html',
                           model=model,
                           model_data=model_meta_data,
                           model_stats_json=model_stats,
                           test_stats_json=test_stats,
                           test_corpus=test_corpus,
                           available_tests=available_tests,
                           link_list=link_list,
                           user_email=user.email if user else "",
                           subscription=subscription,
                           stmts_counts=top_stmts_counts,
                           added_stmts=added_stmts,
                           model_info_contents=model_info_contents,
                           test_info_contents=test_info_contents,
                           model_types=["Test", *[FORMATTED_TYPE_NAMES[mt]
                                                  for mt in
                                                  current_model_types]],
                           new_applied_tests=_new_applied_tests(
                               test_stats, current_model_types, model, date,
                               test_corpus, add_test_links),
                           all_test_results=_format_table_array(
                               all_tests, current_model_types, model, date,
                               test_corpus, add_test_links),
                           new_passed_tests=_new_passed_tests(
                               model, test_stats, current_model_types, date,
                               test_corpus, add_test_links),
                           date=date,
                           latest_date=latest_date,
                           tab=tab,
                           exp_formats=exp_formats,
                           paper_distr=paper_distr,
                           new_papers=new_papers,
                           belief_data=belief_data,
                           agent=agent,
                           agent_info=agent_info,
                           agent_stats=agent_stats,
                           agent_stmts_counts=agent_stmts_counts,
                           agent_added_stmts=agent_added_stmts,
                           agent_paper_distr=agent_paper_distr,
                           agent_tests=agent_tests_table,
                           agent_paths=agent_paths_table,
                           all_agents=all_agents)


@app.route('/annotate_paper/<model>', methods=['GET', 'POST'])
def annotate_paper_statements(model):
    """Upload hypothes.is annotations for a given paper

    Parameters
    ----------
    model : str
        A name of a model to get statements from.
    date : str
        Date in the format "YYYY-MM-DD" to load the model state.
    paper_id : str
        ID of a paper to get statements from.
    paper_id_type : str
        Type of paper ID (e.g. TRID, PMID, PMCID, DOI).
    """
    date = request.args.get('date')
    paper_id = request.args.get('paper_id')
    paper_id_type = request.args.get('paper_id_type')
    if paper_id_type == 'TRID':
        trid = paper_id
    else:
        db = get_db('primary')
        trids = _get_trids(db, paper_id, paper_id_type.lower())
        if trids:
            trid = str(trids[0])
        else:
            abort(Response(f'Invalid paper ID: {paper_id}', 400))
    model_stats = _load_model_stats_from_cache(model, date)
    paper_hashes = model_stats['paper_summary']['stmts_by_paper'][trid]
    paper_stmts = load_stmts_by_hash(model, date, paper_hashes)
    for stmt in paper_stmts:
        stmt.evidence = [ev for ev in stmt.evidence
                         if str(ev.text_refs.get('TRID')) == trid]
    url = None
    for i, stmt in enumerate(paper_stmts):
        logger.info(f'Annotating statement {i + 1} out of {len(paper_stmts)}')
        anns = upload_statement_annotation(stmt)
        if anns:
            url = f"{anns[0]['url']}#annotations:group:{hypothesis_group}"
    if url:
        return {'redirectURL': url}
    else:
        return {'redirectURL': '/no_annotations'}


@app.route('/no_annotations')
def no_annotations():
    return Response('Could not annotate the paper')


@app.route('/statements_from_paper/<model>', methods=['GET', 'POST'])
def get_paper_statements(model):
    """Return statements per paper as JSON or HTML page.

    Parameters
    ----------
    model : str
        A name of a model to get statements from.
    date : str
        Date in the format "YYYY-MM-DD" to load the model state.
    paper_id : str
        ID of a paper to get statements from.
    paper_id_type : str
        Type of paper ID (e.g. TRID, PMID, PMCID, DOI).
    format : str
        Format to return the result as ('json' or 'html').
    """
    display_format = request.args.get('format', 'html')
    if display_format == 'html':
        loaded = request.args.get('loaded')
        loaded = (loaded == 'true')
        if not loaded:
            return render_template(
                'loading.html',
                msg=('Please wait while we load the statements '
                     'from this paper...'))
    date = request.args.get('date')
    paper_id = request.args.get('paper_id')
    paper_id_type = request.args.get('paper_id_type')
    
    if paper_id_type.upper() == 'TRID':
        trid = paper_id
    else:
        db = get_db('primary')
        trids = _get_trids(db, paper_id, paper_id_type.lower())
        if trids:
            trid = str(trids[0])
        else:
            abort(Response(f'Invalid paper ID: {paper_id}', 400))
    model_stats = _load_model_stats_from_cache(model, date)
    raw_paper_ids = model_stats['paper_summary']['raw_paper_ids']
    paper_hashes = model_stats['paper_summary']['stmts_by_paper'].get(trid, [])
    if paper_hashes:
        updated_stmts = [filter_evidence(stmt, trid, 'TRID') for stmt
                         in load_stmts_by_hash(model, date, paper_hashes)]
        updated_stmts = sorted(updated_stmts, key=lambda x: len(x.evidence),
                               reverse=True)
    else:
        updated_stmts = []
    if display_format == 'json':
        resp = {'statements': stmts_to_json(updated_stmts)}
        return resp
    stmt_rows = []
    stmts_by_hash = {}
    for stmt in updated_stmts:
        stmts_by_hash[str(stmt.get_hash(refresh=True))] = stmt
    curations = get_curations(pa_hash=paper_hashes)
    cur_dict = defaultdict(list)
    for cur in curations:
        cur_dict[(cur['pa_hash'], cur['source_hash'])].append(
            {'error_type': cur['tag']})
    cur_counts = _count_curations(curations, stmts_by_hash)
    if len(updated_stmts) > 1:
        with_evid = False
    else:
        with_evid = True
    for stmt in updated_stmts:
        stmt_row = _get_stmt_row(stmt, 'paper', model, cur_counts,
                                 date, None, None, cur_dict, with_evid,
                                 trid, 'TRID')
        stmt_rows.append(stmt_row)
    if not stmt_rows:
        if int(trid) in raw_paper_ids:
            stmt_rows = 'We did not get assembled statements from this paper'
        else:
            stmt_rows = 'We did not process this paper in this model'
    paper_title = _get_title(trid, model_stats)
    table_title = f'Statements from the paper "{paper_title}"'

    fig_list = get_document_figures(paper_id, paper_id_type)
    return render_template('evidence_template.html',
                           stmt_rows=stmt_rows,
                           model=model,
                           source='paper',
                           table_title=table_title,
                           date=date,
                           paper_id=paper_id,
                           paper_id_type=paper_id_type,
                           fig_list=fig_list,
                           tabs=True)


@app.route('/tests/<model>')
def get_model_tests_page(model):
    """Render page displaying results of individual test."""
    loaded = request.args.get('loaded')
    loaded = (loaded == 'true')
    if not loaded:
        return render_template(
            'loading.html',
            msg='Please wait while we load test results...')
    model_type = request.args.get('model_type')
    test_hash = request.args.get('test_hash')
    test_corpus = request.args.get('test_corpus')
    if not test_corpus:
        abort(Response('Test corpus has to be provided', 404))
    date = request.args.get('date')
    if model_type not in ALL_MODEL_TYPES:
        abort(Response(f'Model type {model_type} does not exist', 404))
    test_stats_loaded, file_key = _load_test_stats_from_cache(
        model, test_corpus, date)
    if not test_stats_loaded:
        abort(Response(f'Data for {model} for {date} was not found', 404))
    test_stats = deepcopy(test_stats_loaded)
    try:
        current_test = \
            test_stats['test_round_summary']['all_test_results'][test_hash]
    except KeyError:
        abort(Response(f'Result for this test does not exist for {date}', 404))
    current_model_types = [mt for mt in ALL_MODEL_TYPES if mt in
                           test_stats['test_round_summary']]
    test = current_test["test"]
    test_status, path_list = current_test[model_type]
    correct, incorrect = _label_curations()
    if isinstance(path_list, list):
        for path in path_list:
            for edge in path['edge_list']:
                for stmt in edge['stmts']:
                    cur = ''
                    url = stmt[0]
                    if 'stmt_hash' in url:
                        stmt_hashes = parse.parse_qs(
                            parse.urlparse(url).query)['stmt_hash']
                        cur = _set_curation(stmt_hashes, correct, incorrect)
                    stmt.append(cur)
    latest_date = get_latest_available_date(model, test_corpus)
    prefix = f'stats/{model}/test_stats_{test_corpus}_'
    cur_ix = find_index_of_s3_file(file_key, EMMAA_BUCKET_NAME, prefix)
    if test_hash in test_stats['tests_delta']['applied_hashes_delta']['added']:
        prev_date = None
    elif (cur_ix + 1) < find_number_of_files_on_s3(
            EMMAA_BUCKET_NAME, prefix, '.json'):
        prev_date = last_updated_date(
            model, 'test_stats', 'date', tests=test_corpus, extension='.json',
            n=(cur_ix + 1), bucket=EMMAA_BUCKET_NAME)
    else:
        prev_date = None
    if cur_ix > 0:
        next_date = last_updated_date(
            model, 'test_stats', 'date', tests=test_corpus, extension='.json',
            n=(cur_ix - 1), bucket=EMMAA_BUCKET_NAME)
    else:
        next_date = None
    return render_template('tests_template.html',
                           link_list=link_list,
                           model=model,
                           model_type=model_type,
                           all_model_types=current_model_types,
                           test_hash=test_hash,
                           test=test,
                           test_status=test_status,
                           path_list=path_list,
                           formatted_names=FORMATTED_TYPE_NAMES,
                           date=date,
                           latest_date=latest_date,
                           prev=prev_date,
                           next=next_date)


@app.route('/query')
@jwt_optional
def get_query_page():
    """Render queries page."""
    loaded = request.args.get('loaded')
    loaded = (loaded == 'true')
    if not loaded:
        return render_template(
            'loading.html',
            msg='Please wait while we load the queries...')
    user, roles = resolve_auth(dict(request.args))
    user_email = user.email if user else ""
    tab = request.args.get('tab', 'static')
    model_meta_data = _get_model_meta_data()
    stmt_types = get_queryable_stmt_types()
    preselected_model = request.args.get('preselected')
    latest_query = session.pop('latest_query', None)
    logger.info(f'Prefiling the form with previous values: {latest_query}')

    # Queried immediate results
    immediate_results = {}
    immediate_results['static'] = get_immediate_queries('path_property')
    immediate_results['open'] = get_immediate_queries('open_search_query')
    immediate_results['dynamic'] = get_immediate_queries('dynamic_property')
    immediate_results['intervention'] = get_immediate_queries(
        'simple_intervention_property')

    # Subscribed results
    # user_email = 'joshua@emmaa.com'
    subscribed_results = {}
    subscribed_results['static'] = get_subscribed_queries(
        'path_property', user_email)
    subscribed_results['dynamic'] = get_subscribed_queries(
        'dynamic_property', user_email)
    subscribed_results['open'] = get_subscribed_queries(
        'open_search_query', user_email)
    subscribed_results['intervention'] = get_subscribed_queries(
        'simple_intervention_property', user_email)

    return render_template('query_template.html',
                           model_data=model_meta_data,
                           stmt_types=stmt_types,
                           immediate_results=immediate_results,
                           subscribed_results=subscribed_results,
                           ns_groups=ns_mapping,
                           link_list=link_list,
                           user_email=user_email,
                           tab=tab,
                           preselected_model=preselected_model,
                           latest_query=latest_query)


@app.route('/evidence')
def get_statement_evidence_page():
    """Render page displaying evidence for statement or return statement JSON.
    """
    display_format = request.args.get('format', 'html')
    if display_format == 'html':
        loaded = request.args.get('loaded')
        loaded = (loaded == 'true')
        if not loaded:
            return render_template(
                'loading.html',
                msg='Please wait while we load the statement evidence...')
    stmt_hashes = set(request.args.getlist('stmt_hash'))
    source = request.args.get('source')
    model = request.args.get('model')
    test_corpus = request.args.get('test_corpus', '')
    date = request.args.get('date')
    paper_id = request.args.get('paper_id')
    paper_id_type = request.args.get('paper_id_type')
    stmts = []
    if not date:
        date = get_latest_available_date(model, _default_test(model))
    if source == 'model_statement':
        # Add up paths per statement count across test corpora
        stmt_counts_dict = Counter()
        test_corpora = _get_test_corpora(model)
        for test_corpus in test_corpora:
            test_date = get_latest_available_date(model, test_corpus)
            test_stats, _ = _load_test_stats_from_cache(
                model, test_corpus, test_date)
            stmt_counts = test_stats['test_round_summary'].get(
                'path_stmt_counts', [])
            stmt_counts_dict += Counter(dict(stmt_counts))
        stmts, _ = load_stmts(model, date, stmt_hashes)
    elif source == 'paper':
        stmts = [filter_evidence(stmt, paper_id, paper_id_type) for stmt in
                 load_stmts_by_hash(model, date, stmt_hashes)]
    elif source == 'test':
        if not test_corpus:
            abort(Response(f'Need test corpus name to load evidence', 404))
        tests = _load_tests_from_cache(test_corpus)
        stmt_counts_dict = None
        stmts = [t.stmt for t in tests if
                 str(t.stmt.get_hash(refresh=True)) in stmt_hashes]
    else:
        abort(Response(f'Source should be model_statement or test', 404))
    stmts = sorted(stmts, key=lambda x: len(x.evidence), reverse=True)
    if display_format == 'html':
        stmt_rows = []
        tabs = False
        fig_list = None
        if stmts:
            stmts_by_hash = {str(stmt.get_hash(refresh=True)): stmt
                             for stmt in stmts}
            curations = get_curations(pa_hash=stmt_hashes)
            cur_dict = defaultdict(list)
            for cur in curations:
                cur_dict[(cur['pa_hash'], cur['source_hash'])].append(
                    {'error_type': cur['tag']})
            cur_counts = _count_curations(curations, stmts_by_hash)
            if len(stmts) > 1:
                with_evid = False
            else:
                with_evid = True
                tabs = True
                query = ','.join(
                    [ag.name for ag in stmts[0].real_agent_list()])
                fig_list = get_figures_from_query(query, limit=10)
            for stmt in stmts:
                stmt_row = _get_stmt_row(stmt, source, model, cur_counts, date,
                                         test_corpus, stmt_counts_dict,
                                         cur_dict, with_evid)
                stmt_rows.append(stmt_row)
        else:
            stmt_rows = 'No statements found with this hash'
    else:
        if not stmts:
            return {'error': 'No statements found with this hash'}
        stmt_json = json.dumps(stmts[0].to_json(), indent=1)
        return Response(stmt_json, mimetype='application/json')
    return render_template('evidence_template.html',
                           stmt_rows=stmt_rows,
                           model=model,
                           source=source,
                           test_corpus=test_corpus if test_corpus else None,
                           table_title='Statement Evidence and Curation',
                           msg=None,
                           is_all_stmts=False,
                           date=date,
                           fig_list=fig_list,
                           tabs=tabs)


@app.route('/all_statements/<model>')
def get_all_statements_page(model):
    """Render page with all statements for the model."""
    loaded = request.args.get('loaded')
    loaded = (loaded == 'true')
    if not loaded:
        return render_template(
            'loading.html',
            msg='Please wait while we load the model statements...')
    # Get all arguments
    sort_by = request.args.get('sort_by', 'evidence')
    page = int(request.args.get('page', 1))
    filter_curated = request.args.get('filter_curated', False)
    stmt_types = request.args.getlist('stmt_type')
    if stmt_types:
        stmt_types = [stmt_type.lower() for stmt_type in stmt_types]
    date = request.args.get('date')
    min_belief = request.args.get('min_belief')
    max_belief = request.args.get('max_belief')
    agent = request.args.get('agent')
    if not date:
        date = get_latest_available_date(model, _default_test(model))
    filter_curated = (filter_curated == 'true')
    offset = (page - 1)*1000

    # Load the statements; if they are available in the database, the sorting,
    # offset and limit will be done there; otherwise, the full list will be
    # loaded and sorted here.
    stmts, from_db = load_stmts(model, date, sort_by=sort_by, offset=offset, limit=1000)

    if agent:
        stmts = AgentStatsGenerator.filter_stmts(agent, stmts)
    stmts_by_hash = {str(stmt.get_hash(refresh=True)): stmt for stmt in stmts}
    msg = None
    curations = get_curations()
    cur_counts = _count_curations(curations, stmts_by_hash)

    # Helper function for filtering statements on different conditions
    def filter_stmt(stmt):
        accepted = []
        stmt_hash = str(stmt.get_hash(refresh=True))
        if stmt_types:
            accepted.append(type(stmt).__name__.lower() in stmt_types)
        if filter_curated:
            accepted.append(stmt_hash not in cur_counts)
        if min_belief:
            accepted.append(stmt.belief >= float(min_belief))
        if max_belief:
            accepted.append(stmt.belief <= float(max_belief))
        keep = all(accepted)
        if not keep:
            stmts_by_hash.pop(stmt_hash, None)
        return all(accepted)

    # Filter statements with all filters
    stmts = list(filter(filter_stmt, stmts))

    beliefs = [stmt.belief for stmt in stmts]
    belief_range = round(min(beliefs), 2), round(max(beliefs), 2)

    model_stats = _load_model_stats_from_cache(model, date)
    all_agents = [ag for (ag, count) in
                  model_stats['model_summary']['agent_distr']]
    total_stmts = model_stats['model_summary']['number_of_statements']
    if total_stmts % 1000 == 0:
        total_pages = total_stmts//1000
    else:
        total_pages = total_stmts//1000 + 1
    if page + 1 <= total_pages:
        next_page = page + 1
    else:
        next_page = None
    if page != 1:
        prev_page = page - 1
    else:
        prev_page = None
    if not from_db:
        stmts, stmt_counts_dict = _local_sort_stmts(stmts, offset, sort_by)
    else:
        stmt_counts_dict = load_path_counts(model, date)
    stmt_rows = []
    for stmt in stmts:
        stmt_row = _get_stmt_row(stmt, 'model_statement', model, cur_counts,
                                 date, None, stmt_counts_dict)
        stmt_rows.append(stmt_row)
    table_title = f'All statements in {model.upper()} model.'

    if does_exist(EMMAA_BUCKET_NAME,
                  f'assembled/{model}/latest_statements_{model}'):
        fkey = f'assembled/{model}/latest_statements_{model}.json'
        link = f'https://{EMMAA_BUCKET_NAME}.s3.amazonaws.com/{fkey}'
    elif does_exist(EMMAA_BUCKET_NAME, f'assembled/{model}/statements_'):
        fkey = find_latest_s3_file(
            EMMAA_BUCKET_NAME, f'assembled/{model}/statements_', '.json')
        link = f'https://{EMMAA_BUCKET_NAME}.s3.amazonaws.com/{fkey}'
    else:
        link = None
    return render_template('evidence_template.html',
                           stmt_rows=stmt_rows,
                           model=model,
                           source='model_statement',
                           table_title=table_title,
                           msg=msg,
                           is_all_stmts=True,
                           prev=prev_page,
                           next=next_page,
                           filter_curated=filter_curated,
                           sort_by=sort_by,
                           link=link,
                           date=date,
                           tabs=False,
                           all_stmt_types=get_queryable_stmt_types(),
                           stmt_types=stmt_types,
                           belief_range=belief_range,
                           min_belief=min_belief,
                           max_belief=max_belief,
                           agent=agent,
                           all_agents=all_agents)


@app.route('/demos')
@jwt_optional
def get_demos_page():
    user, roles = resolve_auth(dict(request.args))
    user_email = user.email if user else ""
    return render_template('demos_template.html', link_list=link_list,
                           user_email=user_email)


@app.route('/chat')
@jwt_optional
def chat_with_the_model():
    model = request.args.get('model', '')
    user, roles = resolve_auth(dict(request.args))
    user_email = user.email if user else ""
    return render_template('chat_widget.html',
                           email=user_email,
                           model=model,
                           link_list=link_list,
                           exclude_footer=True,
                           pusher_key=pusher_key)


@app.route('/new/guest', methods=['POST'])
def guest_user():
    data = request.json
    print('New guest data: %s' % str(data))

    pusher.trigger('general-channel', 'new-guest-details', {
        'name': data['name'],
        'email': data['email'],
        'emmaa_model': data.get('emmaa_model')
        })

    return json.dumps(data)


@app.route("/pusher/auth", methods=['POST'])
def pusher_authentication():
    auth = pusher.authenticate(channel=request.form['channel_name'],
                               socket_id=request.form['socket_id'])
    return json.dumps(auth)


@app.route('/query/<model>')
def get_query_tests_page(model):
    """Render page displaying results of individual query."""
    loaded = request.args.get('loaded')
    loaded = (loaded == 'true')
    if not loaded:
        return render_template(
            'loading.html',
            msg='Please wait while we load query results...')
    model_type = request.args.get('model_type')
    query_hash = int(request.args.get('query_hash'))
    order = int(request.args.get('order', 1))
    results = qm.retrieve_results_from_hashes(
        [query_hash], 'path_property', order)
    detailed_results = results[query_hash][model_type]\
        if results else ['query', f'{query_hash}']
    date = results[query_hash]['date'][:10]
    card_title = ('', results[query_hash]['query'] if results else '', '')
    next_order = order - 1 if order > 1 else None
    prev_order = order + 1 if \
        order < qm.db.get_number_of_results(query_hash, model_type) else None
    correct, incorrect = _label_curations()
    path_list = detailed_results[1]
    if isinstance(path_list, list):
        for path in path_list:
            for edge in path['edge_list']:
                for stmt in edge['stmts']:
                    cur = ''
                    url = stmt[0]
                    if 'stmt_hash' in url:
                        stmt_hashes = parse.parse_qs(
                            parse.urlparse(url).query)['stmt_hash']
                        cur = _set_curation(stmt_hashes, correct, incorrect)
                    stmt.append(cur)
    return render_template('tests_template.html',
                           link_list=link_list,
                           model=model,
                           model_type=model_type,
                           all_model_types=ALL_MODEL_TYPES,
                           test_hash=query_hash,
                           test=card_title,
                           is_query_page=True,
                           test_status=detailed_results[0],
                           path_list=path_list,
                           formatted_names=FORMATTED_TYPE_NAMES,
                           date=date,
                           prev=prev_order,
                           next=next_order)


@app.route('/query/submit', methods=['POST'])
@jwt_optional
def process_query():
    """Get result for a query."""
    # Print inputs.
    logger.info('Got model query')
    logger.info("Args -----------")
    logger.info(request.args)
    logger.info("Json -----------")
    logger.info(str(request.json))
    logger.info("------------------")

    user, roles = resolve_auth(dict(request.args))
    user_email = user.email if user else ""
    user_id = user.id if user else None

    # Extract info.
    def get_expected_keys(fields):
        keys = {f'{pos}Selection' for pos in fields}
        keys.update({'queryType'})
        return keys

    expected_static_query_keys = get_expected_keys(
        ['subject', 'object', 'type'])
    expected_dynamic_query_keys = get_expected_keys(
        ['pattern', 'value', 'agent'])
    expected_open_query_keys = get_expected_keys(
        ['openAgent', 'stmtType', 'role', 'ns'])
    expected_models = {mid for mid, _ in _get_model_meta_data()}
    tab = 'static'
    try:
        # If user tries to register query without logging in, refuse query
        # with 401 (unauthorized)
        if request.json['register']:
            if user_email:
                # Logged in
                subscribe = request.json['register']
            else:
                # Not logged in
                logger.warning('User not logged in! Query handling aborted.')
                return jsonify({'result': 'failure',
                                'reason': 'Invalid credentials'}), 401
        # Does not try to register
        else:
            subscribe = False
        query_json = request.json['query']
        assert (set(query_json.keys()) == expected_static_query_keys or
                set(query_json.keys()) == expected_dynamic_query_keys or
                set(query_json.keys()) == expected_open_query_keys), (
            f'Did not get expected query keys: got {set(query_json.keys())} ')
        models = set(request.json.get('models'))
        assert models < expected_models, \
            f'Got unexpected models: {models - expected_models}'
    except (KeyError, AssertionError) as e:
        logger.exception(e)
        logger.error("Invalid query!")
        abort(Response(f'Invalid request: {str(e)}', 400))
    try:
        query, tab = _make_query(query_json)
    except GroundingError as e:
        logger.exception(e)
        logger.error("Invalid grounding!")
        abort(Response(f'Invalid entity: {str(e)}', 400))

    is_test = 'test' in request.json or 'test' == request.json.get('tag')

    if is_test:
        logger.info('Test passed')
        res = {'result': 'test passed', 'ref': None}

    else:
        logger.info('Query submitted')
        try:
            result = qm.answer_immediate_query(
                user_email, user_id, query, models, subscribe)
        except Exception as e:
            logger.exception(e)
            raise(e)
        logger.info('Answer to query received: rendering page, returning '
                    'redirect endpoint')
        redir_url = f'/query?tab={tab}'

        # Replace existing entry
        session['query_hashes'] = result
        session['latest_query'] = {'query_json': query_json,
                                   'models': list(models)}
        res = {'redirectURL': redir_url}

    logger.info('Result: %s' % str(res))
    return Response(json.dumps(res), mimetype='application/json')


@app.route('/query/unsubscribe')
def email_unsubscribe():
    # Get request args which must contain:
    # See:
    # https://stackoverflow.com/questions/1240915/ +
    # how-to-add-one-click-unsubscribe-functionality-to-email-newletters
    # 1. urlencoded email address
    # 2. expiration time of the link (to prevent later unwanted
    #    unsubscribing if email gets in the wrong hands)
    # 3. signature generated by something like
    # signature = encrypt("<encoded-email>" + "<expiration>", "secretkey")
    req_args = request.args.copy()
    email = req_args.get('email')
    expiration = req_args.get('expiration')
    signature = req_args.get('signature', '')

    # Check that required query parameters are present
    if bool(email) and bool(expiration) and bool(signature):
        # Check that expiration is in the future
        not_expired = datetime.utcnow() < datetime.fromtimestamp(int(
            expiration))

    else:
        logger.info('Missing data in query parameters')
        return render_template('email_unsub/bad_email_unsub_link.html',
                               code=400)

    if not_expired:
        logger.info(f'Verifying email unsubscribe request by {email}')
        # Verify signature
        verified = verify_email_signature(signature=signature,
                                          email=email,
                                          expiration=expiration)
    else:
        return render_template('email_unsub/bad_email_unsub_link.html',
                               code=400)

    # Verify that the email exists in the UserQuery table and possibly also
    # that there are subscriptions to actually unsubscribe from
    if verified:
        # queries conatins a list of tuples (english query, query type,
        # query hash)
        subscriptions = get_email_subscriptions(email=email)

        return render_template('email_unsub/email_unsubscribe.html',
                               email=req_args['email'],
                               possible_queries=subscriptions['queries'],
                               possible_models=subscriptions['models'],
                               expiration=expiration,
                               signature=signature)
    else:
        return render_template('email_unsub/bad_email_unsub_link.html',
                               code=400)


@app.route('/query/unsubscribe/submit', methods=['POST'])
def email_unsubscribe_post():
    query = request.json.copy()
    email = query.get('email')
    queries = query.get('queries', [])
    models = query.get('models', [])
    expiration = query.get('expiration')
    signature = query.get('signature')
    logger.info(f'Got unsubscribe request for {email} for queries {queries}'
                f' and models {models}')

    # Check that required query parameters are present
    if bool(email) and bool(expiration) and bool(signature):
        # Check that expiration is in the future
        not_expired = datetime.utcnow() < datetime.fromtimestamp(int(
            expiration))
    else:
        logger.info('signature has expired')
        not_expired = False

    if not_expired:
        verified = verify_email_signature(signature=signature, email=email,
                                          expiration=expiration)
    else:
        logger.info('Failed to verify signature')
        verified = False

    if verified:
        success = register_email_unsubscribe(email, queries, models)
        params = parse.urlencode(
            {'email': email, 'expiration': expiration, 'signature': signature})
        return jsonify({'redirectURL': f'/query/unsubscribe?{params}'})
    else:
        logger.info('Could not verify signature, aborting unsubscribe')
        return jsonify({'result': False, 'reason': 'Invalid signature'}), 401


@app.route('/subscribe/<model>', methods=['POST'])
@jwt_optional
def model_subscription(model):
    user, roles = resolve_auth(dict(request.args))
    if not roles and not user:
        logger.warning('User is not logged in')
        res_dict = {"result": "failure", "reason": "Invalid Credentials"}
        return jsonify(res_dict), 401

    user_email = user.email
    user_id = user.id

    subscribe = request.json.get('subscribe')
    logger.info(f'Change subscription status for {model} and {user_email} to '
                f'{subscribe}')
    if subscribe:
        qm.db.subscribe_to_model(user_email, user_id, model)
        return {'subscription': 'success'}
    else:
        qm.db.update_email_subscription(user_email, [], [model], False)
        return {'unsubscribe': 'success'}


@app.route('/statements/from_hash/<model>/<date>/<hash_val>', methods=['GET'])
def get_statement_by_hash_model(model, date, hash_val):
    """Get model statement JSON by hash."""
    stmts = load_stmts_by_hash(model, date, [hash_val])
    st_json = {}
    curations = get_curations(pa_hash=hash_val)
    cur_dict = defaultdict(list)
    for cur in curations:
        cur_dict[(cur['pa_hash'], cur['source_hash'])].append(
            {'error_type': cur['tag']})
    for st in stmts:
        if str(st.get_hash(refresh=True)) == str(hash_val):
            st_json = st.to_json()
            ev_list = _format_evidence_text(
                st, cur_dict, ['correct', 'act_vs_amt', 'hypothesis'])
            st_json['evidence'] = ev_list
    return {'statements': {hash_val: st_json}}


@app.route('/tests/from_hash/<test_corpus>/<hash_val>', methods=['GET'])
def get_tests_by_hash(test_corpus, hash_val):
    """Get test statement JSON by hash."""
    tests = _load_tests_from_cache(test_corpus)
    curations = get_curations(pa_hash=hash_val)
    cur_dict = defaultdict(list)
    for cur in curations:
        cur_dict[(cur['pa_hash'], cur['source_hash'])].append(
            {'error_type': cur['tag']})
    st_json = {}
    for test in tests:
        if str(test.stmt.get_hash(refresh=True)) == str(hash_val):
            st_json = test.stmt.to_json()
            ev_list = _format_evidence_text(
                test.stmt, cur_dict, ['correct', 'act_vs_amt', 'hypothesis'])
            st_json['evidence'] = ev_list
    return {'statements': {hash_val: st_json}}


@app.route('/statements/from_paper/<model>/<paper_id>/<paper_id_type>/'
           '<date>/<hash_val>', methods=['GET'])
def get_statement_by_paper(model, paper_id, paper_id_type, date, hash_val):
    """Get model statement by hash and paper ID."""
    stmts = load_stmts_by_hash(model, date, [hash_val])
    st_json = {}
    curations = get_curations(pa_hash=hash_val)
    cur_dict = defaultdict(list)
    for cur in curations:
        cur_dict[(cur['pa_hash'], cur['source_hash'])].append(
            {'error_type': cur['tag']})
    for st in stmts:
        if str(st.get_hash(refresh=True)) == str(hash_val):
            stmt = filter_evidence(st, paper_id, paper_id_type)
            st_json = stmt.to_json()
            ev_list = _format_evidence_text(
                stmt, cur_dict, ['correct', 'act_vs_amt', 'hypothesis'])
            st_json['evidence'] = ev_list
    return {'statements': {hash_val: st_json}}


@app.route('/curation/submit/<hash_val>', methods=['POST'])
@jwt_optional
def submit_curation_endpoint(hash_val, **kwargs):
    user, roles = resolve_auth(dict(request.args))
    if not roles and not user:
        res_dict = {"result": "failure", "reason": "Invalid Credentials"}
        return jsonify(res_dict), 401

    if user:
        email = user.email
    else:
        email = request.json.get('email')
        if not email:
            res_dict = {"result": "failure",
                        "reason": "POST with API key requires a user email."}
            return jsonify(res_dict), 400

    logger.info("Adding curation for statement %s." % hash_val)
    ev_hash = request.json.get('ev_hash')
    source_api = request.json.pop('source', 'EMMAA')
    tag = request.json.get('tag')
    ip = request.remote_addr
    text = request.json.get('text')
    is_test = 'test' in request.args
    if not is_test:
        assert tag != 'test'
        try:
            dbid = submit_curation(hash_val, tag, email, ip, text, ev_hash,
                                   source_api)
        except BadHashError as e:
            abort(Response("Invalid hash: %s." % e.mk_hash, 400))
        res = {'result': 'success', 'ref': {'id': dbid}}
    else:
        res = {'result': 'test passed', 'ref': None}
    logger.info("Got result: %s" % str(res))
    return jsonify(res)


@app.route('/curation/list/<stmt_hash>/<src_hash>', methods=['GET'])
def list_curations(stmt_hash, src_hash):
    curations = get_curations(pa_hash=stmt_hash, source_hash=src_hash)
    return jsonify(curations)


# REST API endpoints

@latest_ns.param('model', 'Name of EMMAA model, e.g. aml, covid19, etc.')
@latest_ns.route('/statements/<model>')
class LatestStatements(Resource):
    @latest_ns.response(200, 'INDRA Statements', stmts_model)
    def get(self, model):
        """Return model latest statements and link to S3 latest statements file."""
        stmts, fkey = get_assembled_statements(model, bucket=EMMAA_BUCKET_NAME)
        stmt_jsons = stmts_to_json(stmts)
        link = f'https://{EMMAA_BUCKET_NAME}.s3.amazonaws.com/{fkey}'
        return {'statements': stmt_jsons, 'link': link}


@latest_ns.param('model', 'Name of EMMAA model, e.g. aml, covid19, etc.')
@latest_ns.expect(url_parser)
@latest_ns.route('/statements_url/<model>')
class LatestStatementsUrl(Resource):
    @latest_ns.marshal_with(link_model)
    def get(self, model):
        """Return a link to model latest statements file on S3."""
        dated = request.args.get('dated', type=inputs.boolean)
        fkey = None
        if dated:
            prefix = f'assembled/{model}/statements_'
            fkey = find_latest_s3_file(EMMAA_BUCKET_NAME, prefix, '.gz')
        else:
            if does_exist(EMMAA_BUCKET_NAME,
                          f'assembled/{model}/latest_statements_{model}'):
                fkey = f'assembled/{model}/latest_statements_{model}.json'
        if fkey:
            link = f'https://{EMMAA_BUCKET_NAME}.s3.amazonaws.com/{fkey}'
        else:
            link = None
        return {'link': link}


@latest_ns.expect(date_parser)
@latest_ns.route('/stats_date/<model>')
class LatestStatsDate(Resource):
    @latest_ns.marshal_with(date_model)
    def get(self, model):
        """Get latest date for which both model and test stats are available"""
        date_format = request.args.get('date_format', 'datetime')
        test_corpus = request.args.get(
            'test_corpus', _default_test(model))
        date = get_latest_available_date(
            model, test_corpus, date_format=date_format,
            bucket=EMMAA_BUCKET_NAME)
        return {'model': model, 'test_corpus': test_corpus, 'date': date}


@latest_ns.param('model', 'Name of EMMAA model, e.g. aml, covid19, etc.')
@latest_ns.route('/curated_statements/<model>')
class CuratedStatements(Resource):
    @latest_ns.marshal_with(curations_model)
    def get(self, model):
        """Get hashes of curated statements by category."""
        model_stats = _load_model_stats_from_cache(model, None)
        stmt_hashes = set(model_stats['model_summary']['all_stmts'].keys())
        correct, incorrect, partial = _label_curations(include_partial=True,
                                                       pa_hash=stmt_hashes)
        return {'correct': list(correct),
                'partial': list(partial),
                'incorrect': list(incorrect)}


@metadata_ns.route('/models')
class ModelsList(Resource):
    @metadata_ns.marshal_with(models_model)
    def get(self):
        """Get a list of all available models."""
        model_meta_data = _get_model_meta_data()
        models = [model for (model, config) in model_meta_data]
        return {'models': models}


@metadata_ns.param('model', 'Name of EMMAA model, e.g. aml, covid19, etc.')
@metadata_ns.route('/model_info/<model>')
class ModelInfo(Resource):
    @metadata_ns.marshal_with(model_info_model, skip_none=True)
    def get(self, model):
        """Get metadata for model."""
        config = get_model_config(model)
        info = {'name': model,
                'human_readable_name': config.get('human_readable_name'),
                'description': config.get('description')}
        if 'ndex' in config:
            info['ndex'] = config['ndex'].get('network')
        if 'twitter_link' in config:
            info['twitter'] = config['twitter_link']
        if 'dynamic' in config['assembly']:
            info['stmts_for_dynamic_key'] = f'{model}_dynamic'
        return info


@metadata_ns.param('model', 'Name of EMMAA model, e.g. aml, covid19, etc.')
@metadata_ns.route('/test_corpora/<model>')
class TestCorpora(Resource):
    @metadata_ns.marshal_with(test_corpora_model)
    def get(self, model):
        """Get a list of available test corpora for model."""
        tests = _get_test_corpora(model)
        return {'test_corpora': list(tests)}


@metadata_ns.param('test_corpus',
                   'Name of test corpus, e.g. covid19_mitre_tests')
@metadata_ns.route('/tests_info/<test_corpus>')
class TestInfo(Resource):
    @metadata_ns.marshal_with(test_info_model, skip_none=True)
    def get(self, test_corpus):
        """Get test corpus metadata."""
        model_meta_data = _get_model_meta_data()
        tested_model = None
        for (model, config) in model_meta_data:
            tests = _get_test_corpora(model)
            if test_corpus in tests:
                tested_model = model
                break
        if not tested_model:
            restx_abort(404, f'Test info for {test_corpus} is not available')
        test_stats, _ = _load_test_stats_from_cache(tested_model, test_corpus)
        info = test_stats['test_round_summary'].get('test_data')
        if not info:
            restx_abort(404, f'Test info for {test_corpus} is not available')
        return info


@metadata_ns.param('model', 'Name of EMMAA model, e.g. aml, covid19, etc.')
@metadata_ns.expect(entity_parser)
@metadata_ns.route('/entity_info/<model>')
class EntityInfo(Resource):
    @metadata_ns.response(200, 'Information about entity',
                          model=entity_info_model)
    def get(self, model):
        """Get information about an entity."""
        # For now, the model isn't explicitly used but could be necessary
        # for adding model-specific entity info later
        namespace = request.args.get('namespace')
        identifier = request.args.get('id')
        rv = get_entity_info(namespace, identifier)
        return rv


@query_ns.expect(path_query_model)
@query_ns.route('/source_target_path')
class SourceTargetPath(Resource):
    @query_ns.marshal_with(path_result_model, skip_none=True)
    def post(self):
        """Explain an effect between source and target."""
        model = request.get_json().get('model')
        if not model:
            restx_abort(400, 'Provide a "model"')
        source = request.get_json().get('source')
        target = request.get_json().get('target')
        if not source or not target:
            msg = ('Provide a "source" and a "target" '
                   '(formatted as INDRA Agent JSONs).')
            restx_abort(400, msg)
        source = Agent._from_json(source)
        target = Agent._from_json(target)
        stmt_type = request.get_json().get('stmt_type')
        if not stmt_type:
            msg = 'Provide a "stmt_type" (one of INDRA Statement types).'
            restx_abort(400, msg)
        stmt_class = get_statement_by_name(stmt_type)
        stmt = stmt_class(source, target)
        query = PathProperty(stmt)
        return _run_query(query, model)


@query_ns.expect(open_query_model)
@query_ns.route('/up_down_stream_path')
class UpDownStreamPath(Resource):
    @query_ns.marshal_with(path_result_model, skip_none=True)
    def post(self):
        """Find causal paths to or from a given entity."""
        model = request.get_json().get('model')
        if not model:
            restx_abort(400, 'Provide a "model"')
        entity = request.get_json().get('entity')
        if not entity:
            msg = 'Provide an "entity" (formatted as INDRA Agent JSON).'
            restx_abort(400, msg)
        entity = Agent._from_json(entity)
        entity_role = request.get_json().get('entity_role')
        if not entity_role or entity_role not in ('subject', 'object'):
            msg = ('Provide an "entity_role" ("subject" for downstream or '
                   '"object" for upstream search).')
            restx_abort(400, msg)
        stmt_type = request.get_json().get('stmt_type')
        if not stmt_type:
            msg = 'Provide a "stmt_type" (one of INDRA Statement types).'
        terminal_ns = request.get_json().get('terminal_ns')
        query = OpenSearchQuery(entity, stmt_type, entity_role, terminal_ns)
        return _run_query(query, model)


@query_ns.expect(dynamic_query_model)
@query_ns.route('/temporal_dynamic')
class TemporalDynamic(Resource):
    @query_ns.marshal_with(dynamic_result_model)
    def post(self):
        """Simulate a model to verify if a certain pattern is met.
        """
        model = request.get_json().get('model')
        if not model:
            restx_abort(400, 'Provide a "model"')
        entity = request.get_json().get('entity')
        if not entity:
            msg = 'Provide an "entity" (formatted as INDRA Agent JSON).'
            restx_abort(400, msg)
        entity = Agent._from_json(entity)
        pattern_type = request.get_json().get('pattern_type')
        acceptable_patterns = ('always_value', 'sometime_value',
                               'eventual_value', 'no_change', 'sustained',
                               'transient')
        if not pattern_type or pattern_type not in acceptable_patterns:
            msg = f'Provide "pattern_type" (one of {acceptable_patterns})'
        if pattern_type in acceptable_patterns[3:]:
            quant_value = None
        else:
            quant_value = request.get_json().get('quant_value')
            if not quant_value:
                msg = (f'{pattern_type} pattern type requires a '
                       '"quant_value" ("high" or "low")')
                restx_abort(400, msg)
        query = DynamicProperty(entity, pattern_type, quant_value)
        return _run_query(query, model)


@query_ns.expect(intervention_query_model)
@query_ns.route('/source_target_dynamic')
class SourceTargetDynamic(Resource):
    @query_ns.marshal_with(interv_result_model)
    def post(self):
        """Simulate a model to describe the effect of an intervention."""
        model = request.get_json().get('model')
        if not model:
            restx_abort(400, 'Provide a "model"')
        source = request.get_json().get('source')
        target = request.get_json().get('target')
        if not source or not target:
            msg = ('Provide a "source" and a "target" '
                   '(formatted as INDRA Agent JSONs).')
            restx_abort(400, msg)
        source = Agent._from_json(source)
        target = Agent._from_json(target)
        direction = request.get_json().get('direction')
        if not direction:
            restx_abort(400, 'Provide a "direction" ("up" or "dn")')
        query = SimpleInterventionProperty(source, target, direction)
        return _run_query(query, model)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Run the EMMAA dashboard service.')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', default=5000, type=int)
    parser.add_argument('--preload', action='store_true')
    args = parser.parse_args()

    # TODO: make pre-loading available when running service via Gunicorn
    if args.preload and not GLOBAL_PRELOAD:
        # Load all the model configs
        model_meta_data = _get_model_meta_data()
        # Load all the model mamangers for queries
        for model, _ in model_meta_data:
            load_model_manager_from_cache(model)

    print(app.url_map)  # Get all avilable urls and link them
    app.run(host=args.host, port=args.port)
