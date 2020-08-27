import os
import json
import boto3
import logging
import argparse
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from flask import abort, Flask, request, Response, render_template, jsonify,\
    session
from flask_jwt_extended import jwt_optional
from urllib import parse
from collections import defaultdict

from indra.statements import get_all_descendants, IncreaseAmount, \
    DecreaseAmount, Activation, Inhibition, AddModification, \
    RemoveModification, get_statement_by_name
from indra.assemblers.html.assembler import _format_evidence_text, \
    _format_stmt_text
from indra_db.client.principal.curation import get_curations, submit_curation

from emmaa.util import find_latest_s3_file, strip_out_date, does_exist, \
    EMMAA_BUCKET_NAME, list_s3_files, find_index_of_s3_file, \
    find_number_of_files_on_s3, load_json_from_s3
from emmaa.model import load_config_from_s3, last_updated_date, \
    get_model_stats, _default_test, get_assembled_statements
from emmaa.model_tests import load_tests_from_s3
from emmaa.answer_queries import QueryManager, load_model_manager_from_cache, \
    FORMATTED_TYPE_NAMES
from emmaa.subscription.email_util import verify_email_signature,\
    register_email_unsubscribe, get_email_subscriptions
from emmaa.queries import PathProperty, get_agent_from_text, GroundingError, \
    DynamicProperty, OpenSearchQuery

from indralab_auth_tools.auth import auth, config_auth, resolve_auth
from indralab_web_templates.path_templates import path_temps

app = Flask(__name__)
app.register_blueprint(auth)
app.register_blueprint(path_temps)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = os.environ.get('EMMAA_SERVICE_SESSION_KEY', '')
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


def get_latest_available_date(model, test_corpus, bucket=EMMAA_BUCKET_NAME):
    if not test_corpus:
        logger.error('Test corpus is missing, cannot find latest date')
        return
    model_date = last_updated_date(model, 'model_stats', extension='.json',
                                   bucket=bucket)
    test_date = last_updated_date(model, 'test_stats', tests=test_corpus,
                                  extension='.json', bucket=bucket)
    if model_date == test_date:
        logger.info(f'Latest available date for {model} model and '
                    f'{test_corpus} is {model_date}.')
        return model_date
    min_date = min(model_date, test_date)
    if is_available(model, test_corpus, min_date, bucket=bucket):
        logger.info(f'Latest available date for {model} model and '
                    f'{test_corpus} is {min_date}.')
        return min_date
    min_date_obj = datetime.strptime(min_date, "%Y-%m-%d")
    for day_count in range(1, 30):
        earlier_date = min_date_obj - timedelta(days=day_count)
        if is_available(model, test_corpus, earlier_date, bucket=bucket):
            logger.info(f'Latest available date for {model} model and '
                        f'{test_corpus} is {earlier_date}.')
            return earlier_date
    logger.info(f'Could not find latest available date for {model} model '
                f'and {test_corpus}.')


def _get_test_corpora(model, bucket=EMMAA_BUCKET_NAME):
    all_files = list_s3_files(bucket, f'stats/{model}/test_stats_', '.json')
    tests = set([os.path.basename(key)[11:-25] for key in all_files])
    return tests


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
                       test_corpus):
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
                               test_corpus)


def _format_table_array(tests_json, model_types, model_name, date,
                        test_corpus):
    # tests_json needs to have the structure: [(test_hash, tests)]
    table_array = []
    for th, test in tests_json:
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
                      test_corpus):
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
    curations = get_curations(**kwargs)
    correct_tags = ['correct', 'act_vs_amt', 'hypothesis']
    correct = {str(c.pa_hash) for c in curations if c.tag in correct_tags}
    incorrect = {str(c.pa_hash) for c in curations if
                 str(c.pa_hash) not in correct}
    return correct, incorrect


def _count_curations(curations, stmts_by_hash):
    correct_tags = ['correct', 'act_vs_amt', 'hypothesis']
    cur_counts = {}
    for cur in curations:
        stmt_hash = str(cur.pa_hash)
        if stmt_hash not in stmts_by_hash:
            continue
        if stmt_hash not in cur_counts:
            cur_counts[stmt_hash] = {
                'this': defaultdict(int),
                'other': defaultdict(int),
            }
        if cur.tag in correct_tags:
            cur_tag = 'correct'
        else:
            cur_tag = 'incorrect'
        if cur.source_hash in [evid.get_source_hash() for evid in
                               stmts_by_hash[stmt_hash].evidence]:
            cur_source = 'this'
        else:
            cur_source = 'other'
        cur_counts[stmt_hash][cur_source][cur_tag] += 1
    return cur_counts


def _get_stmt_row(stmt, source, model, cur_counts, date, test_corpus=None,
                  path_counts=None, cur_dict=None, with_evid=False):
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
    test_corpus = request.args.get('test_corpus', _default_test(
        model, get_model_config(model)))
    if not test_corpus:
        abort(Response('Could not identify test corpus', 404))
    date = request.args.get('date', get_latest_available_date(
        model, test_corpus))
    tab = request.args.get('tab', 'model')
    user, roles = resolve_auth(dict(request.args))
    model_meta_data = _get_model_meta_data()
    model_stats, _ = get_model_stats(model, 'model', date=date)
    test_stats, _ = get_model_stats(model, 'test', tests=test_corpus,
                                    date=date)
    if not model_stats or not test_stats:
        abort(Response(f'Data for {model} and {test_corpus} for {date} '
                       f'was not found', 404))
    ndex_id = 'None available'
    description = 'None available'
    for mid, mmd in model_meta_data:
        if mid == model:
            ndex_id = mmd['ndex']['network']
            description = mmd['description']
    if ndex_id == 'None available':
        logger.warning(f'No ndex ID found for {model}')
    available_tests = _get_test_corpora(model)
    latest_date = get_latest_available_date(model, test_corpus)
    model_info_contents = [
        [('', 'Model Description', ''), ('', description, '')],
        [('', 'Latest Data Available', ''), ('', latest_date, '')],
        [('', 'Data Displayed', ''),
         ('', date,
          'Click on the point on time graph to see earlier results')],
        [('', 'Network on Ndex', ''),
         (f'http://www.ndexbio.org/#/network/{ndex_id}', ndex_id,
          'Click to see network on Ndex')]]
    test_data = test_stats['test_round_summary'].get('test_data')
    test_info_contents = None
    if test_data:
        test_info_contents = [[('', k.capitalize(), ''), ('', v, '')]
                              for k, v in test_data.items()]
    current_model_types = [mt for mt in ALL_MODEL_TYPES if mt in
                           test_stats['test_round_summary']]
    # Get correct and incorrect curation hashes to pass it per stmt
    correct, incorrect = _label_curations()
    # Filter out rows with all tests == 'n_a'
    all_tests = []
    for k, v in test_stats['test_round_summary']['all_test_results'].items():
        cur = _set_curation(k, correct, incorrect)
        v['test'].append(cur)
        if all(v[mt][0].lower() == 'n_a' for mt in current_model_types):
            continue
        else:
            all_tests.append((k, v))

    all_stmts = model_stats['model_summary']['all_stmts']
    for st_hash, st_value in all_stmts.items():
        url_param = parse.urlencode(
            {'stmt_hash': st_hash, 'source': 'model_statement', 'model': model,
             'date': date})
        st_value[0] = f'/evidence?{url_param}'
        st_value[2] = stmt_db_link_msg
        cur = _set_curation(st_hash, correct, incorrect)
        st_value.append(cur)
    most_supported = model_stats['model_summary']['stmts_by_evidence'][:10]
    top_stmts_counts = [((all_stmts[h]), ('', str(c), ''))
                        for h, c in most_supported]
    added_stmts_hashes = \
        model_stats['model_delta']['statements_hashes_delta']['added']
    if len(added_stmts_hashes) > 0:
        added_stmts = [((all_stmts[h]),) for h in added_stmts_hashes]
    else:
        added_stmts = 'No new statements were added'
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
                               test_corpus),
                           all_test_results=_format_table_array(
                               all_tests, current_model_types, model, date,
                               test_corpus),
                           new_passed_tests=_new_passed_tests(
                               model, test_stats, current_model_types, date,
                               test_corpus),
                           date=date,
                           latest_date=latest_date,
                           tab=tab)


@app.route('/tests/<model>')
def get_model_tests_page(model):
    model_type = request.args.get('model_type')
    test_hash = request.args.get('test_hash')
    test_corpus = request.args.get('test_corpus')
    if not test_corpus:
        abort(Response('Test corpus has to be provided', 404))
    date = request.args.get('date')
    if model_type not in ALL_MODEL_TYPES:
        abort(Response(f'Model type {model_type} does not exist', 404))
    test_stats, file_key = get_model_stats(
        model, 'test', tests=test_corpus, date=date)
    if not test_stats:
        abort(Response(f'Data for {model} for {date} was not found', 404))
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
    user, roles = resolve_auth(dict(request.args))
    user_email = user.email if user else ""
    tab = request.args.get('tab', 'model')
    model_meta_data = _get_model_meta_data()
    stmt_types = get_queryable_stmt_types()

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
                           tab=tab)


@app.route('/evidence')
def get_statement_evidence_page():
    stmt_hashes = request.args.getlist('stmt_hash')
    source = request.args.get('source')
    model = request.args.get('model')
    test_corpus = request.args.get('test_corpus', '')
    date = request.args.get('date')
    display_format = request.args.get('format', 'html')
    stmts = []
    if source == 'model_statement':
        test_stats, _ = get_model_stats(model, 'test')
        stmt_counts = test_stats['test_round_summary'].get(
            'path_stmt_counts', [])
        stmt_counts_dict = dict(stmt_counts)
        all_stmts = _load_stmts_from_cache(model, date)
        for stmt in all_stmts:
            for stmt_hash in stmt_hashes:
                if str(stmt.get_hash()) == str(stmt_hash):
                    stmts.append(stmt)
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
            cur_dict[(cur.pa_hash, cur.source_hash)].append(
                {'error_type': cur.tag})
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
    sort_by = request.args.get('sort_by', 'evidence')
    page = int(request.args.get('page', 1))
    filter_curated = request.args.get('filter_curated', False)
    date = request.args.get('date')
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
    test_stats, _ = get_model_stats(model, 'test')
    stmt_counts = test_stats['test_round_summary'].get('path_stmt_counts', [])
    stmt_counts_dict = dict(stmt_counts)
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
        if not stmt_counts:
            msg = 'Sorting by paths is not available, sorting by evidence'
            stmts = sorted(stmts, key=lambda x: len(x.evidence), reverse=True)[
                offset:offset+1000]
        else:
            stmts = []
            for (stmt_hash, count) in stmt_counts[offset:offset+1000]:
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
    stmts = _load_stmts_from_cache(model, date)
    st_json = {}
    curations = get_curations(pa_hash=hash_val)
    cur_dict = defaultdict(list)
    for cur in curations:
        cur_dict[(cur.pa_hash, cur.source_hash)].append(
            {'error_type': cur.tag})
    for st in stmts:
        if str(st.get_hash()) == str(hash_val):
            st_json = st.to_json()
            ev_list = _format_evidence_text(
                st, cur_dict, ['correct', 'act_vs_amt', 'hypothesis'])
            st_json['evidence'] = ev_list
    return {'statements': {hash_val: st_json}}


@app.route('/tests/from_hash/<test_corpus>/<hash_val>', methods=['GET'])
def get_tests_by_hash(test_corpus, hash_val):
    tests = _load_tests_from_cache(test_corpus)
    curations = get_curations(pa_hash=hash_val)
    cur_dict = defaultdict(list)
    for cur in curations:
        cur_dict[(cur.pa_hash, cur.source_hash)].append(
            {'error_type': cur.tag})
    st_json = {}
    for test in tests:
        if str(test.stmt.get_hash()) == str(hash_val):
            st_json = test.stmt.to_json()
            ev_list = _format_evidence_text(
                test.stmt, cur_dict, ['correct', 'act_vs_amt', 'hypothesis'])
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
    curation_json = [cur.to_json() for cur in curations]
    return jsonify(curation_json)


@app.route('/latest_statements/<model>', methods=['GET'])
def load_latest_statements(model):
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
