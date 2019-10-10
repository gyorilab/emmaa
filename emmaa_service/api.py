import re
import json
import boto3
import logging
import argparse
from botocore.exceptions import ClientError
from flask import abort, Flask, request, Response, render_template, jsonify,\
    session
from flask_jwt_extended import jwt_optional

from indra.config import CONFIG_DICT
from indra.statements import get_all_descendants, IncreaseAmount, \
    DecreaseAmount, Activation, Inhibition, AddModification, \
    RemoveModification, get_statement_by_name

from emmaa.util import find_latest_s3_file, strip_out_date, get_s3_client
from emmaa.model import load_config_from_s3
from emmaa.answer_queries import QueryManager, load_model_manager_from_s3
from emmaa.queries import PathProperty, get_agent_from_text, GroundingError
from emmaa.answer_queries import FORMATTED_TYPE_NAMES

from indralab_auth_tools.auth import auth, config_auth, resolve_auth
from indralab_web_templates.path_templates import path_temps

app = Flask(__name__)
app.register_blueprint(auth)
app.register_blueprint(path_temps)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = CONFIG_DICT['EMMAA_SERVICE_SESSION_KEY']
logger = logging.getLogger(__name__)


TITLE = 'emmaa title'
EMMAA_BUCKET_NAME = 'emmaa'
ALL_MODEL_TYPES = ['pysb', 'pybel', 'signed_graph', 'unsigned_graph']
LINKAGE_SYMBOLS = {'LEFT TACK': '\u22a3',
                   'RIGHTWARDS ARROW': '\u2192'}
link_list = [('/home', 'EMMAA Dashboard'),
             ('/query', 'Queries')]
pass_fail_msg = 'Click to see detailed results for this test'
stmt_db_link_msg = 'Click to see the evidence for this statement'
SC, jwt = config_auth(app)
qm = QueryManager()


def _sort_pass_fail(r):
    return tuple(r[n+1][1] for n in range(len(r)-1))


def _get_model_meta_data():
    s3 = boto3.client('s3')
    resp = s3.list_objects(Bucket=EMMAA_BUCKET_NAME, Prefix='models/',
                           Delimiter='/')
    model_data = []
    for pref in resp['CommonPrefixes']:
        model = pref['Prefix'].split('/')[1]
        config_json = get_model_config(model)
        if not config_json:
            continue
        model_data.append((model, config_json))
    return model_data


def get_model_config(model):
    if model in model_cache:
        return model_cache[model]
    try:
        config_json = load_config_from_s3(model)
        model_cache[model] = config_json
    except ClientError:
        logger.warning(f"Model {model} has no metadata. Skipping...")
        return None
    if 'human_readable_name' not in config_json.keys():
        logger.warning(f"Model {model} has no readable name. Skipping...")
        model_cache[model] = None
    return model_cache[model]


def get_model_stats(model, extension='.json'):
    """Gets the latest statistics for the given model

    Parameters
    ----------
    model : str
        Model name to look for
    extension : str

    Returns
    -------
    model_data : json
        The json formatted data containing the statistics for the model
    """
    s3 = get_s3_client()

    # Need jsons for model meta data and test statistics. File name examples:
    # stats/skcm/stats_2019-08-20-17-34-40.json
    prefix = f'stats/{model}/stats_'
    latest_file_key = find_latest_s3_file(bucket=EMMAA_BUCKET_NAME,
                                          prefix=prefix,
                                          extension=extension)
    model_data_object = s3.get_object(Bucket=EMMAA_BUCKET_NAME,
                                      Key=latest_file_key)
    return json.loads(model_data_object['Body'].read().decode('utf8'))


def model_last_updated(model, extension='.pkl'):
    """Find the most recent pickle file of model and return its creation date

    Example file name:
    models/aml/model_2018-12-13-18-11-54.pkl

    Parameters
    ----------
    model : str
        Model name to look for
    extension : str
        The extension the model file needs to have. Default is '.pkl'

    Returns
    -------
    last_updated : str
        A string of the format "YYYY-MM-DD-HH-mm-ss"
    """
    prefix = f'models/{model}/model_'
    try:
        return strip_out_date(find_latest_s3_file(
            bucket=EMMAA_BUCKET_NAME,
            prefix=prefix,
            extension=extension
        ))
    except TypeError:
        logger.info('Could not find latest update date')
        return ''


GLOBAL_PRELOAD = False
model_cache = {}
if GLOBAL_PRELOAD:
    # Load all the model configs
    model_meta_data = _get_model_meta_data()
    # Load all the model managers for queries
    for model, _ in model_meta_data:
        load_model_manager_from_s3(model)


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


def _make_query(query_dict, use_grouding_service=True):
    stmt_type = query_dict['typeSelection']
    stmt_class = get_statement_by_name(stmt_type)
    subj = get_agent_from_text(
        query_dict['subjectSelection'], use_grouding_service)
    obj = get_agent_from_text(
        query_dict['objectSelection'], use_grouding_service)
    stmt = stmt_class(subj, obj)
    query = PathProperty(path_stmt=stmt)
    return query


def _extract_stmt_link(anchor_string):
    # Matches an anchor with at least an href attribute
    pattern = '<a.*? href="(.*?)".*?>(.*?)</a>'
    m = re.search(pattern=pattern, string=anchor_string)
    if m:
        return m.group(1), m.group(2)
    else:
        return '', anchor_string


def _new_applied_tests(model_stats_json, model_types, model_name):
    # Extract new applied tests into:
    #   list of tests (one per row)
    #       each test is a list of tuples (one tuple per column)
    #           each tuple is a (href, link_text) pair
    all_test_results = model_stats_json['test_round_summary'][
        'all_test_results']
    new_app_hashes = model_stats_json['tests_delta']['applied_hashes_delta'][
        'added']
    if len(new_app_hashes) == 0:
        return 'No new tests were applied'
    new_app_tests = [(th, all_test_results[th]) for th in new_app_hashes]
    return _format_table_array(new_app_tests, model_types, model_name)


def _format_table_array(tests_json, model_types, model_name):
    # tests_json needs to have the structure: [(test_hash, tests)]
    table_array = []
    for th, test in tests_json:
        new_row = [(*test['test'], stmt_db_link_msg)
                   if len(test['test']) == 2 else test['test']]
        for mt in model_types:
            new_row.append((f'/tests/{model_name}/{mt}/{th}', test[mt][0],
                            pass_fail_msg))
        table_array.append(new_row)
    return sorted(table_array, reverse=True, key=_sort_pass_fail)


def _format_query_results(formatted_results):
    result_array = []
    for qh, res in formatted_results.items():
        model_types = [mt for mt in ALL_MODEL_TYPES if mt in res]
        model = res['model']
        new_res = [('', res["query"], ''),
                   (f'/dashboard/{model}', model,
                    f'Click to see details about {model}')]
        for mt in model_types:
            new_res.append((f'/tests/{model}/{mt}/{qh}', res[mt][0],
                            'Click to see detailed results for this query'))
        result_array.append(new_res)
    return result_array


def _new_passed_tests(model_name, model_stats_json, current_model_types):
    new_passed_tests = []
    all_test_results = model_stats_json['test_round_summary'][
        'all_test_results']
    for mt in current_model_types:
        new_passed_hashes = model_stats_json['tests_delta'][mt][
            'passed_hashes_delta']['added']
        if not new_passed_hashes:
            continue
        mt_rows = [[('', f'New passed tests for '
                         f'{FORMATTED_TYPE_NAMES[mt]} model.',
                     '')]]
        for test_hash in new_passed_hashes:
            test = all_test_results[test_hash]
            path_loc = test[mt][1]
            if isinstance(path_loc, list):
                path = path_loc[0]['path']
            else:
                path = path_loc
            new_row = [(*test['test'], stmt_db_link_msg)
                       if len(test['test']) == 2 else test['test'],
                       (f'/tests/{model_name}/{mt}/{test_hash}', path,
                        pass_fail_msg)]
            mt_rows.append(new_row)
        new_passed_tests += mt_rows
    if len(new_passed_tests) > 0:
        return new_passed_tests
    return 'No new tests were passed'


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
    user, roles = resolve_auth(dict(request.args))
    model_meta_data = _get_model_meta_data()

    last_update = model_last_updated(model=model)
    ndex_id = 'None available'
    for mid, mmd in model_meta_data:
        if mid == model:
            ndex_id = mmd['ndex']['network']
    if ndex_id == 'None available':
        logger.warning(f'No ndex ID found for {model}')
    if not last_update:
        logger.warning(f'Could not get last update for {model}')
        last_update = 'Not available'
    model_info_contents = [
        [('', 'Last Updated', ''), ('', last_update, '')],
        [('', 'Network on Ndex', ''),
         (f'http://www.ndexbio.org/#/network/{ndex_id}', ndex_id,
          'Click to see network on Ndex')]]
    model_stats = get_model_stats(model)
    all_new_tests = [(k, v) for k, v in model_stats['test_round_summary'][
        'all_test_results'].items()]
    current_model_types = [mt for mt in ALL_MODEL_TYPES if mt in
                           model_stats['test_round_summary']]
    all_stmts = model_stats['model_summary']['all_stmts']
    most_supported = model_stats['model_summary']['stmts_by_evidence'][:10]
    top_stmts_counts = [((*all_stmts[h], stmt_db_link_msg)
                         if len(all_stmts[h]) == 2 else all_stmts[h],
                         ('', str(c), '')) for h, c in most_supported]
    added_stmts_hashes = \
        model_stats['model_delta']['statements_hashes_delta']['added']
    if len(added_stmts_hashes) > 0:
        added_stmts = [[(*all_stmts[h], stmt_db_link_msg)
                        if len(all_stmts[h]) == 2 else all_stmts[h]] for h in
                       added_stmts_hashes]
    else:
        added_stmts = 'No new statements were added'
    return render_template('model_template.html',
                           model=model,
                           model_data=model_meta_data,
                           model_stats_json=model_stats,
                           link_list=link_list,
                           user_email=user.email if user else "",
                           stmts_counts=top_stmts_counts,
                           added_stmts=added_stmts,
                           model_info_contents=model_info_contents,
                           model_types=["Test", *[FORMATTED_TYPE_NAMES[mt]
                                                  for mt in
                                                  current_model_types]],
                           new_applied_tests=_new_applied_tests(
                               model_stats_json=model_stats,
                               model_types=current_model_types,
                               model_name=model),
                           all_test_results=_format_table_array(
                               tests_json=all_new_tests,
                               model_types=current_model_types,
                               model_name=model),
                           new_passed_tests=_new_passed_tests(
                               model, model_stats, current_model_types))


@app.route('/tests/<model>/<model_type>/<test_hash>')
def get_model_tests_page(model, model_type, test_hash):
    if model_type not in ALL_MODEL_TYPES:
        abort(Response(f'Model type {model_type} does not exist', 404))
    model_stats = get_model_stats(model)
    current_test = \
        model_stats['test_round_summary']['all_test_results'][test_hash]
    current_model_types = [mt for mt in ALL_MODEL_TYPES if mt in
                           model_stats['test_round_summary']]
    test = current_test["test"]
    test_status, path_list = current_test[model_type]
    return render_template('tests_template.html',
                           link_list=link_list,
                           model=model,
                           model_type=model_type,
                           all_model_types=current_model_types,
                           test_hash=test_hash,
                           model_stats_json=model_stats,
                           test=test,
                           test_status=test_status,
                           path_list=path_list,
                           formatted_names=FORMATTED_TYPE_NAMES)


@app.route('/query')
@jwt_optional
def get_query_page():
    user, roles = resolve_auth(dict(request.args))
    user_email = user.email if user else ""
    model_meta_data = _get_model_meta_data()
    stmt_types = get_queryable_stmt_types()

    if session.get('raw_query_result'):
        res = list(session['raw_query_result'].values())[0]
        immediate_table_headers =\
            ['Query', 'Model', *[mt for mt in ALL_MODEL_TYPES if mt in res]]
    else:
        immediate_table_headers = None
    # Subscribed results
    # user_email = 'joshua@emmaa.com'
    if user_email:
        sub_res = qm.get_registered_queries(user_email)
        if sub_res:
            subscribed_results = _format_query_results(sub_res)
        else:
            subscribed_results = 'You have no subscribed queries'
    else:
        subscribed_results = 'Please log in to see your subscribed queries'
    subscribed_headers =\
        ['Model', 'Query'] + \
        [mt for mt in list(subscribed_results.values())[0]
         if mt in ALL_MODEL_TYPES] if subscribed_results else []
    return render_template('query_template.html',
                           immediate_table_headers=immediate_table_headers,
                           model_data=model_meta_data,
                           stmt_types=stmt_types,
                           subscribed_results=subscribed_results,
                           subscribed_headers=subscribed_headers,
                           link_list=link_list,
                           user_email=user_email)


@app.route('/query/<model>/<model_type>/<query_hash>')
def get_query_tests_page(model, model_type, query_hash):
    raw_query_json = session['raw_query_result']
    detailed_results = raw_query_json[query_hash][model_type]
    return render_template('tests_template.html',
                           link_list=link_list,
                           model=model,
                           model_type=model_type,
                           all_model_types=ALL_MODEL_TYPES,
                           test_hash=query_hash,
                           model_stats_json=raw_query_json,
                           test=('', raw_query_json['query'], 'No link'),
                           test_status=detailed_results[0],
                           path_list=detailed_results[1],
                           formatted_names=FORMATTED_TYPE_NAMES)


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
    expected_query_keys = {f'{pos}Selection'
                           for pos in ['subject', 'object', 'type']}
    expected_models = {mid for mid, _ in _get_model_meta_data()}
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
        assert set(query_json.keys()) == expected_query_keys, \
            (f'Did not get expected query keys: got {set(query_json.keys())} '
             f'not {expected_query_keys}')
        models = set(request.json.get('models'))
        assert models < expected_models, \
            f'Got unexpected models: {models - expected_models}'
    except (KeyError, AssertionError) as e:
        logger.exception(e)
        logger.error("Invalid query!")
        abort(Response(f'Invalid request: {str(e)}', 400))
    try:
        query = _make_query(query_json)
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
        redir_url = '/query'

        # Replace existing entry
        session['immediate_query_result'] = _format_query_results(result)
        session['raw_query_result'] = result
        res = {'redirectURL': redir_url}

    logger.info('Result: %s' % str(res))
    return Response(json.dumps(res), mimetype='application/json')


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
            load_model_manager_from_s3(model)

    print(app.url_map)  # Get all avilable urls and link them
    app.run(host=args.host, port=args.port)
