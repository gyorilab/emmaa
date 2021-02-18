import os
import json
import boto3
import logging
import argparse
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from flask import abort, Flask, request, Response, render_template, jsonify,\
    session
from flask_cors import CORS

from flask_jwt_extended import jwt_optional
from urllib import parse
from collections import defaultdict, Counter
from copy import deepcopy
from pusher import pusher

from indra_db.exceptions import BadHashError
from indra_db import get_db
from indra_db.util import _get_trids
from indra.statements import get_all_descendants, IncreaseAmount, \
    DecreaseAmount, Activation, Inhibition, AddModification, \
    RemoveModification, get_statement_by_name, stmts_to_json
from indra.assemblers.html.assembler import _format_evidence_text, \
    _format_stmt_text
from indra_db.client.principal.curation import get_curations, submit_curation

from emmaa.util import find_latest_s3_file, does_exist, \
    EMMAA_BUCKET_NAME, list_s3_files, find_index_of_s3_file, \
    find_number_of_files_on_s3, load_json_from_s3, FORMATTED_TYPE_NAMES
from emmaa.model import load_config_from_s3, last_updated_date, \
    get_model_stats, _default_test, get_assembled_statements
from emmaa.model_tests import load_tests_from_s3
from emmaa.answer_queries import QueryManager, load_model_manager_from_cache
from emmaa.subscription.email_util import verify_email_signature,\
    register_email_unsubscribe, get_email_subscriptions
from emmaa.queries import PathProperty, get_agent_from_text, GroundingError, \
    DynamicProperty, OpenSearchQuery, Query

from indralab_auth_tools.auth import auth, config_auth, resolve_auth
from indralab_web_templates.path_templates import path_temps
from indra.sources.hypothesis import upload_statement_annotation


app = Flask(__name__)
app.register_blueprint(auth)
app.register_blueprint(path_temps)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = os.environ.get('EMMAA_SERVICE_SESSION_KEY', '')
CORS(app)
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
    latest_on_s3 = find_latest_s3_file(
        EMMAA_BUCKET_NAME, f'tests/{test_corpus}', '.pkl')
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
    if 'typeSelection' in query_dict.keys():
        stmt_type = query_dict['typeSelection']
        stmt_class = get_statement_by_name(stmt_type)
        subj = get_agent_from_text(
            query_dict['subjectSelection'])
        obj = get_agent_from_text(
            query_dict['objectSelection'])
        stmt = stmt_class(subj, obj)
        query = PathProperty(path_stmt=stmt)
        tab = 'static'
    elif 'patternSelection' in query_dict.keys():
        agent = get_agent_from_text(query_dict['agentSelection'])
        value = query_dict['valueSelection']
        if not value:
            value = None
        pattern = query_dict['patternSelection']
        query = DynamicProperty(agent, pattern, value)
        tab = 'dynamic'
    elif 'openAgentSelection' in query_dict.keys():
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
        tab = 'open'
        query = OpenSearchQuery(agent, stmt_type, role, terminal_ns)
    return query, tab


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
        mt_rows = [[('', f'New passed tests for '
                         f'{FORMATTED_TYPE_NAMES[mt]} model.',
                     '')]]
        for th in new_passed_hashes:
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
        new_passed_tests += mt_rows
    if len(new_passed_tests) > 0:
        return new_passed_tests
    return 'No new tests were passed'


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


def _label_curations(**kwargs):
    logger.info('Getting curations')
    curations = get_curations(**kwargs)
    logger.info('Labeling curations')
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


def _get_stmt_row(stmt, source, model, cur_counts, date, test_corpus=None,
                  path_counts=None, cur_dict=None, with_evid=False,
                  paper_id=None, paper_id_type=None):
    stmt_hash = str(stmt.get_hash())
    english = _format_stmt_text(stmt)
    evid_count = len(stmt.evidence)
    evid = []
    if with_evid and cur_dict is not None:
        evid = _format_evidence_text(
            stmt, cur_dict, ['correct', 'act_vs_amt', 'hypothesis'])[:10]
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
    badges = _make_badges(evid_count, json_link, path_count,
                          cur_counts.get(stmt_hash))
    stmt_row = [
        (stmt.get_hash(), english, evid, evid_count, badges)]
    return stmt_row


def _make_badges(evid_count, json_link, path_count, cur_counts=None):
    badges = [
        {'label': 'stmt_json', 'num': 'JSON', 'color': '#b3b3ff',
         'symbol': None, 'title': 'View statement JSON', 'href': json_link,
         'loc': 'right'},
        {'label': 'evidence', 'num': evid_count, 'color': 'grey',
         'symbol': None, 'title': 'Evidence count for this statement',
         'loc': 'right'},
        {'label': 'paths', 'num': path_count, 'symbol': '\u2691',
         'color': '#0099ff', 'title': 'Number of paths with this statement'}]
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
    if id_to_title:
        title = id_to_title.get(str(paper_id), 'Title not available')
    else:
        title = 'Title not available'
    return title


def _get_paper_title_tuple(paper_id, model_stats, date):
    title = _get_title(paper_id, model_stats)
    stmts_by_paper_id = model_stats['paper_summary']['stmts_by_paper']
    stmt_hashes = [
        str(st_hash) for st_hash in stmts_by_paper_id.get(str(paper_id), [])]
    if not stmt_hashes:
        url = None
    else:
        model = model_stats['model_summary']['model_name']
        url_param = parse.urlencode(
            {'paper_id': paper_id, 'paper_id_type': 'trid', 'date': date})
        url = f'/statements_from_paper/{model}?{url_param}'
    if url:
        paper_tuple = (url, title, 'Click to see statements from this paper')
    # DB url for statements from paper will be available soon
    # https://db.indra.bio/statements/from_paper/<id_type>/<id_value>
    else:
        paper_tuple = ('', title, '')
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
    user, roles = resolve_auth(dict(request.args))
    model_data = _get_model_meta_data()
    return render_template('index_template.html', model_data=model_data,
                           link_list=link_list,
                           user_email=user.email if user else "")


@app.route('/dashboard/<model>')
@jwt_optional
def get_model_dashboard(model):
    """Render model dashboard page."""
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

    exp_formats = _get_available_formats(model, date, EMMAA_BUCKET_NAME)

    if not model_stats['paper_summary'].get('paper_titles'):
        paper_distr = 'Paper titles are not currently available'
        new_papers = 'Paper titles are not currently available'
    else:
        trids_counts = model_stats['paper_summary']['paper_distr'][:10]
        paper_distr = [[_get_paper_title_tuple(paper_id, model_stats, date),
                        _get_external_paper_link(model, paper_id, model_stats),
                        ('', str(c), '')] for paper_id, c in trids_counts]
        new_papers = get_new_papers(model, model_stats, date)

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
                           new_papers=new_papers)


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
    all_stmts = _load_stmts_from_cache(model, date)
    model_stats = _load_model_stats_from_cache(model, date)
    paper_hashes = model_stats['paper_summary']['stmts_by_paper'][trid]
    paper_stmts = [stmt for stmt in all_stmts
                   if stmt.get_hash() in paper_hashes]
    for stmt in paper_stmts:
        stmt.evidence = [ev for ev in stmt.evidence
                         if str(ev.text_refs.get('TRID')) == trid]
    url = None
    for i, stmt in enumerate(paper_stmts):
        logger.info(f'Annotating statement {i + 1} out of {len(paper_stmts)}')
        anns = upload_statement_annotation(stmt)
        if anns:
            url = anns[0]['url']
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
    date = request.args.get('date')
    paper_id = request.args.get('paper_id')
    paper_id_type = request.args.get('paper_id_type')
    display_format = request.args.get('format', 'html')
    if paper_id_type == 'TRID':
        trid = paper_id
    else:
        db = get_db('primary')
        trids = _get_trids(db, paper_id, paper_id_type.lower())
        if trids:
            trid = str(trids[0])
        else:
            abort(Response(f'Invalid paper ID: {paper_id}', 400))
    all_stmts = _load_stmts_from_cache(model, date)
    model_stats = _load_model_stats_from_cache(model, date)
    paper_hashes = model_stats['paper_summary']['stmts_by_paper'][trid]
    paper_stmts = [stmt for stmt in all_stmts
                   if stmt.get_hash() in paper_hashes]
    updated_stmts = [filter_evidence(stmt, trid, 'TRID')
                     for stmt in paper_stmts]
    updated_stmts = sorted(updated_stmts, key=lambda x: len(x.evidence),
                           reverse=True)
    if display_format == 'json':
        resp = {'statements': stmts_to_json(updated_stmts)}
        return resp
    stmt_rows = []
    stmts_by_hash = {}
    for stmt in updated_stmts:
        stmts_by_hash[str(stmt.get_hash())] = stmt
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
    paper_title = _get_title(trid, model_stats)
    table_title = f'Statements from the paper "{paper_title}"'
    return render_template('evidence_template.html',
                           stmt_rows=stmt_rows,
                           model=model,
                           source='paper',
                           table_title=table_title,
                           date=date,
                           paper_id=paper_id,
                           paper_id_type=paper_id_type)


@app.route('/tests/<model>')
def get_model_tests_page(model):
    """Render page displaying results of individual test."""
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
        elif query_type == 'dynamic_property':
            headers = ['Query', 'Model', 'Result', 'Image']
            results = _format_dynamic_query_results(qr)
    return headers, results


def get_subscribed_queries(query_type, user_email=None):
    headers = []
    if user_email:
        res = qm.get_registered_queries(user_email, query_type)
        if res:
            if query_type in ['path_property', 'open_search_query']:
                sub_results = _format_query_results(res)
                headers = ['Query', 'Model'] + [
                    FORMATTED_TYPE_NAMES[mt] for mt in ALL_MODEL_TYPES]
            elif query_type == 'dynamic_property':
                sub_results = _format_dynamic_query_results(res)
                headers = ['Query', 'Model', 'Result', 'Image']
        else:
            sub_results = 'You have no subscribed queries'
    else:
        sub_results = 'Please log in to see your subscribed queries'
    return headers, sub_results


@app.route('/query')
@jwt_optional
def get_query_page():
    """Render queries page."""
    user, roles = resolve_auth(dict(request.args))
    user_email = user.email if user else ""
    tab = request.args.get('tab', 'model')
    model_meta_data = _get_model_meta_data()
    stmt_types = get_queryable_stmt_types()
    preselected_name = None
    preselected_val = request.args.get('preselected')
    if preselected_val:
        for model, config in model_meta_data:
            if model == preselected_val:
                preselected_name = config['human_readable_name']
                break
    # Queried results
    immediate_table_headers, queried_results = get_immediate_queries(
        'path_property')
    open_headers, open_results = get_immediate_queries('open_search_query')
    dynamic_immediate_headers, dynamic_results = get_immediate_queries(
        'dynamic_property')

    # Subscribed results
    # user_email = 'joshua@emmaa.com'
    subscribed_path_headers, subscribed_path_results = get_subscribed_queries(
        'path_property', user_email)
    subscribed_dyn_headers, subscribed_dyn_results = get_subscribed_queries(
        'dynamic_property', user_email)
    subscribed_open_headers, subscribed_open_results = get_subscribed_queries(
        'open_search_query', user_email)
    return render_template('query_template.html',
                           immediate_table_headers=immediate_table_headers,
                           immediate_query_result=queried_results,
                           immediate_dynamic_results=dynamic_results,
                           dynamic_immediate_headers=dynamic_immediate_headers,
                           open_immediate_headers=open_headers,
                           open_immediate_results=open_results,
                           model_data=model_meta_data,
                           stmt_types=stmt_types,
                           subscribed_results=subscribed_path_results,
                           subscribed_headers=subscribed_path_headers,
                           subscribed_dynamic_headers=subscribed_dyn_headers,
                           subscribed_dynamic_results=subscribed_dyn_results,
                           subscribed_open_headers=subscribed_open_headers,
                           subscribed_open_results=subscribed_open_results,
                           ns_groups=ns_mapping,
                           link_list=link_list,
                           user_email=user_email,
                           tab=tab,
                           preselected_val=preselected_val,
                           preselected_name=preselected_name)


@app.route('/run_query', methods=['POST'])
def run_query():
    """Run a query.

    Parameters
    ----------
    query_json : str(dict)
        A JSON dump of a standard query JSON representation. The structure of
        a query json depends on a query type. All query JSONs have to contain
        a "type" (path_property, dynamic_property, or open_search_query).

        Path (static) query JSON has to contain keys "type" (path_property)
        and "path" (formatted as INDRA Statement JSON).

        Open search query JSON has to contain keys "type" (open_search_query),
        "entity" (formatted as INDRA Agent JSON), "entity_role" (subject or
        object), and "stmt_type"; optionally "terminal_ns" (a list of
        namespaces to filter the result).

        Dynamic query JSON has to contain keys "type" (dynamic_property),
        "entity" (formatted as INDRA Agent JSON), "pattern_type" (one of
        "always_value", "no_change", "eventual_value", "sometime_value",
        "sustained", "transient"), and "quant_value" ("high" or "low", only
        required when "pattern_type" is one of "always_value",
        "eventual_value", "sometime_value").
    model : str
        A name of a model to run a query against.

    Returns
    -------
    results : dict
        A dictionary mapping the model type to either paths or result code.
    """
    qj = request.json.get('query_json')
    if 'type' not in qj:
        msg = ('All query JSONs have to contain a "type" '
               '(path_property, dynamic_property, or open_search_query).')
        abort(Response(msg, 400))
    if qj['type'] == 'path_property':
        msg = ('Path (static) query JSON has to contain keys "type" and "path"'
               ' (formatted as INDRA Statement JSON).')
        if 'path' not in qj:
            abort(Response(msg, 400))
    elif qj['type'] == 'open_search_query':
        msg = ('Open search query JSON has to contain keys "type", "entity" '
               '(formatted as INDRA Agent JSON), "entity_role" (subject or '
               'object), and "stmt_type"; optionally "terminal_ns" (a list of '
               'namespaces to filter the result).')
        if 'entity' not in qj or 'entity_role' not in qj or \
                'stmt_type' not in qj:
            abort(Response(msg, 400))
    elif qj['type'] == 'dynamic_property':
        msg = ('Dynamic query JSON has to contain keys "type", "entity" '
               '(formatted as INDRA Agent JSON), "pattern_type" (one of '
               '"always_value", "no_change", "eventual_value", '
               '"sometime_value", "sustained", "transient"), and "quant_value"'
               ' ("high" or "low", only required when "pattern_type" is one of'
               ' "always_value", "eventual_value", "sometime_value".')
        if 'entity' not in qj or 'pattern_type' not in qj:
            abort(Response(msg, 400))
    model = request.json.get('model')
    query = Query._from_json(qj)
    mm = load_model_manager_from_cache(model)
    full_results = mm.answer_query(query)
    results = {}
    for mc_type, resp, paths in full_results:
        if mc_type:
            results[mc_type] = paths
        else:
            results['all_types'] = paths
    return results


@app.route('/evidence')
def get_statement_evidence_page():
    """Render page displaying evidence for statement or return statement JSON.
    """
    stmt_hashes = request.args.getlist('stmt_hash')
    source = request.args.get('source')
    model = request.args.get('model')
    test_corpus = request.args.get('test_corpus', '')
    date = request.args.get('date')
    display_format = request.args.get('format', 'html')
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
        all_stmts = _load_stmts_from_cache(model, date)
        for stmt in all_stmts:
            for stmt_hash in stmt_hashes:
                if str(stmt.get_hash()) == str(stmt_hash):
                    stmts.append(stmt)
    elif source == 'paper':
        all_stmts = _load_stmts_from_cache(model, date)
        for stmt in all_stmts:
            for stmt_hash in stmt_hashes:
                if str(stmt.get_hash()) == str(stmt_hash):
                    stmts.append(filter_evidence(stmt, paper_id, paper_id_type))
    elif source == 'test':
        if not test_corpus:
            abort(Response(f'Need test corpus name to load evidence', 404))
        tests = _load_tests_from_cache(test_corpus)
        stmt_counts_dict = None
        for t in tests:
            for stmt_hash in stmt_hashes:
                if str(t.stmt.get_hash()) == str(stmt_hash):
                    stmts.append(t.stmt)
    else:
        abort(Response(f'Source should be model_statement or test', 404))
    if display_format == 'html':
        stmt_rows = []
        stmts_by_hash = {}
        for stmt in stmts:
            stmts_by_hash[str(stmt.get_hash())] = stmt
        curations = get_curations(pa_hash=stmt_hashes)
        cur_dict = defaultdict(list)
        for cur in curations:
            cur_dict[(cur['pa_hash'], cur['source_hash'])].append(
                {'error_type': cur['tag']})
        cur_counts = _count_curations(curations, stmts_by_hash)
        for stmt in stmts:
            stmt_row = _get_stmt_row(stmt, source, model, cur_counts, date,
                                     test_corpus, stmt_counts_dict,
                                     cur_dict, True)
            stmt_rows.append(stmt_row)
    else:
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
                           date=date)


@app.route('/all_statements/<model>')
def get_all_statements_page(model):
    """Render page with all statements for the model."""
    sort_by = request.args.get('sort_by', 'evidence')
    page = int(request.args.get('page', 1))
    filter_curated = request.args.get('filter_curated', False)
    date = request.args.get('date')
    if not date:
        date = get_latest_available_date(model, _default_test(model))
    filter_curated = (filter_curated == 'true')
    offset = (page - 1)*1000
    stmts = _load_stmts_from_cache(model, date)
    stmts_by_hash = {}
    for stmt in stmts:
        stmts_by_hash[str(stmt.get_hash())] = stmt
    msg = None
    curations = get_curations()
    cur_counts = _count_curations(curations, stmts_by_hash)
    if filter_curated:
        stmts = [stmt for stmt in stmts if str(stmt.get_hash()) not in
                 cur_counts]
    # Add up paths per statement count across test corpora
    stmt_counts_dict = Counter()
    test_corpora = _get_test_corpora(model)
    for test_corpus in test_corpora:
        test_stats, _ = _load_test_stats_from_cache(model, test_corpus, date)
        stmt_counts = test_stats['test_round_summary'].get(
            'path_stmt_counts', [])
        stmt_counts_dict += Counter(dict(stmt_counts))
    stmt_count_sorted = sorted(
        stmt_counts_dict.items(), key=lambda x: x[1], reverse=True)
    if len(stmts) % 1000 == 0:
        total_pages = len(stmts)//1000
    else:
        total_pages = len(stmts)//1000 + 1
    if page + 1 <= total_pages:
        next_page = page + 1
    else:
        next_page = None
    if page != 1:
        prev_page = page - 1
    else:
        prev_page = None
    if sort_by == 'evidence':
        stmts = sorted(stmts, key=lambda x: len(x.evidence), reverse=True)[
            offset:offset+1000]
    elif sort_by == 'paths':
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
                           date=date)


@app.route('/query/<model>')
def get_query_tests_page(model):
    """Render page displaying results of individual query."""
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
    expected_static_query_keys = {f'{pos}Selection'
                                  for pos in ['subject', 'object', 'type']}
    expected_dynamic_query_keys = {f'{pos}Selection'
                                   for pos in ['pattern', 'value', 'agent']}
    expected_open_query_keys = {f'{pos}Selection' for pos in
                                ['openAgent', 'stmtType', 'role', 'ns']}
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
                user_email, user_id, query, models, subscribe, use_kappa=False)
        except Exception as e:
            logger.exception(e)
            raise(e)
        logger.info('Answer to query received: rendering page, returning '
                    'redirect endpoint')
        redir_url = f'/query?tab={tab}'

        # Replace existing entry
        session['query_hashes'] = result
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
        queries = get_email_subscriptions(email=email)

        return render_template('email_unsub/email_unsubscribe.html',
                               email=req_args['email'],
                               possible_queries=queries,
                               expiration=expiration,
                               signature=signature)
    else:
        return render_template('email_unsub/bad_email_unsub_link.html',
                               code=400)


@app.route('/query/unsubscribe/submit', methods=['POST'])
def email_unsubscribe_post():
    query = request.json.copy()
    email = query.get('email')
    queries = query.get('queries')
    expiration = query.get('expiration')
    signature = query.get('signature')
    logger.info(f'Got unsubscribe request for {email} for queries {queries}')

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
        success = register_email_unsubscribe(email, queries)
        return jsonify({'result': success})
    else:
        logger.info('Could not verify signature, aborting unsubscribe')
        return jsonify({'result': False, 'reason': 'Invalid signature'}), 401


@app.route('/statements/from_hash/<model>/<date>/<hash_val>', methods=['GET'])
def get_statement_by_hash_model(model, date, hash_val):
    """Get model statement JSON by hash."""
    stmts = _load_stmts_from_cache(model, date)
    st_json = {}
    curations = get_curations(pa_hash=hash_val)
    cur_dict = defaultdict(list)
    for cur in curations:
        cur_dict[(cur['pa_hash'], cur['source_hash'])].append(
            {'error_type': cur['tag']})
    for st in stmts:
        if str(st.get_hash()) == str(hash_val):
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
        if str(test.stmt.get_hash()) == str(hash_val):
            st_json = test.stmt.to_json()
            ev_list = _format_evidence_text(
                test.stmt, cur_dict, ['correct', 'act_vs_amt', 'hypothesis'])
            st_json['evidence'] = ev_list
    return {'statements': {hash_val: st_json}}


@app.route('/statements/from_paper/<model>/<paper_id>/<paper_id_type>/'
           '<date>/<hash_val>', methods=['GET'])
def get_statement_by_paper(model, paper_id, paper_id_type, date, hash_val):
    """Get model statement by hash and paper ID."""
    stmts = _load_stmts_from_cache(model, date)
    st_json = {}
    curations = get_curations(pa_hash=hash_val)
    cur_dict = defaultdict(list)
    for cur in curations:
        cur_dict[(cur['pa_hash'], cur['source_hash'])].append(
            {'error_type': cur['tag']})
    for st in stmts:
        if str(st.get_hash()) == str(hash_val):
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
        assert tag is not 'test'
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


@app.route('/latest_statements/<model>', methods=['GET'])
def load_latest_statements(model):
    """Return model latest statements and link to S3 latest statements file."""
    if does_exist(EMMAA_BUCKET_NAME,
                  f'assembled/{model}/latest_statements_{model}'):
        fkey = f'assembled/{model}/latest_statements_{model}.json'
    elif does_exist(EMMAA_BUCKET_NAME, f'assembled/{model}/statements_'):
        fkey = find_latest_s3_file(
            EMMAA_BUCKET_NAME, f'assembled/{model}/statements_', '.json')
    else:
        fkey = None
    if fkey:
        stmt_jsons = load_json_from_s3(EMMAA_BUCKET_NAME, fkey)
        link = f'https://{EMMAA_BUCKET_NAME}.s3.amazonaws.com/{fkey}'
    else:
        stmt_jsons = []
        link = ''
    return {'statements': stmt_jsons, 'link': link}


@app.route('/latest_statements_url/<model>', methods=['GET'])
def get_latest_statements_url(model):
    """Return a link to model latest statements file on S3."""
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
    return {'link': link}


@app.route('/latest_date', methods=['GET'])
def get_latest_date():
    """Return latest available date of model and test stats.

    Parameters
    ----------
    model : str
        Name of the model.
    test_corpus : Optional[str]
        Which test corpus stats to check. If not provided, default test corpus
        for the model is used.
    date_format : Optional[str]
        Which format of the date to return: 'date' or 'datetime'. Default:
        datetime.

    Returns
    -------
    json : dict
        A dictionary with key 'date' and value of a latest available date in a
        selected format.
    """
    model = request.json.get('model')
    if not model:
        abort(Response('Need to provide model', 404))
    date_format = request.json.get('date_format', 'datetime')
    test_corpus = request.json.get('test_corpus', _default_test(model))
    date = get_latest_available_date(
        model, test_corpus, date_format=date_format, bucket=EMMAA_BUCKET_NAME)
    return jsonify({'date': date})


@app.route('/demos')
@jwt_optional
def get_demos_page():
    user, roles = resolve_auth(dict(request.args))
    user_email = user.email if user else ""
    return render_template('demos_template.html', link_list=link_list,
                           user_email=user_email)


@app.route('/models', methods=['GET', 'POST'])
def get_models():
    """Get a list of all available models."""
    model_meta_data = _get_model_meta_data()
    models = [model for (model, config) in model_meta_data]
    return {'models': models}


@app.route('/model_info/<model>', methods=['GET', 'POST'])
def get_model_info(model):
    """Get metadata for model."""
    config = get_model_config(model)
    info = {'name': model,
            'human_readable_name': config.get('human_readable_name'),
            'description': config.get('description')}
    if 'ndex' in config:
        info['ndex'] = config['ndex'].get('network')
    if 'twitter_link' in config:
        info['twitter'] = config['twitter_link']
    return info


@app.route('/test_corpora/<model>', methods=['GET', 'POST'])
def get_tests(model):
    """Get a list of available test corpora for model."""
    tests = _get_test_corpora(model)
    return {'test_corpora': list(tests)}


@app.route('/tests_info/<test_corpus>', methods=['GET', 'POST'])
def get_tests_info(test_corpus):
    """Get test corpus metadata."""
    model_meta_data = _get_model_meta_data()
    for (model, config) in model_meta_data:
        tests = _get_test_corpora(model)
        if test_corpus in tests:
            tested_model = model
            break
    test_stats, _ = _load_test_stats_from_cache(tested_model, test_corpus)
    info = test_stats['test_round_summary'].get('test_data')
    if not info:
        info = {'error': f'Test info for {test_corpus} is not available'}
    return info


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
