import re
import json
import boto3
import logging
import argparse
from urllib import parse
from botocore.exceptions import ClientError
from flask import abort, Flask, request, Response, render_template, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_optional

from indra.statements import get_all_descendants, IncreaseAmount, \
    DecreaseAmount, Activation, Inhibition, AddModification, \
    RemoveModification, get_statement_by_name

from emmaa.db import get_db
from emmaa.util import find_latest_s3_file, strip_out_date, get_s3_client
from emmaa.model import load_config_from_s3
from emmaa.answer_queries import QueryManager, load_model_manager_from_s3
from emmaa.queries import PathProperty, get_agent_from_text, GroundingError

from indralab_auth_tools.auth import auth, config_auth, resolve_auth
from indralab_web_templates.path_templates import path_temps

app = Flask(__name__)
app.register_blueprint(auth)
app.register_blueprint(path_temps)
app.config['DEBUG'] = True
logger = logging.getLogger(__name__)


TITLE = 'emmaa title'
EMMAA_BUCKET_NAME = 'emmaa-test'
ALL_MODEL_TYPES = ['pysb', 'pybel', 'signed_graph', 'unsigned_graph']
LINKAGE_SYMBOLS = {'LEFT TACK': '\u22a3',
                   'RIGHTWARDS ARROW': '\u2192'}
FORMATTED_MODEL_NAMES = {'pysb': 'PySB',
                         'pybel': 'PyBEL',
                         'signed_graph': 'Signed Graph',
                         'unsigned_graph': 'Unsigned Graph'}
link_list = [('./home', 'EMMAA Dashboard'),
             ('./query', 'Queries')]
SC, jwt = config_auth(app)
qm = QueryManager(db=get_db('dev'))


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


def _fix_top_stmts(english_by_hash, top_statements):
    res = []
    for h, c in top_statements:
        html_string = english_by_hash[h]
        res.append((_extract_stmt_link(html_string), ('', str(c))))
    return res


def _extract_stmt_link(anchor_string):
    # Matches an anchor with at least an href attribute
    pattern = '<a.*? href="(.*?)".*?>(.*?)</a>'
    m = re.search(pattern=pattern, string=anchor_string)
    if m:
        return (m.group(1), m.group(2))
    else:
        return ('', anchor_string)


def _get_test_results(stats_json, model_id, test_hash):
    # This is a helper function that mostly makes sure the path_list has the
    # right structure. As we gradually change the json structure,
    # this function should handle less and less of the json structuring.
    # Returns the results for the test with hash test_hash for model type
    # model_type.

    def _format_path_list(unformatted_path_list):
        formatted_path_list = []
        for path in unformatted_path_list:
            path_dict = {"edge_list": []}
            path_string = ""
            for n, edge in enumerate(path):
                href, txt = _extract_stmt_link(edge)
                query_dict = parse.parse_qs(href.split('?')[1])
                subj = query_dict['subject'][0]
                obj = query_dict['object'][0]
                path_string += f"{subj}-{obj}" if n == 0 else f"-{obj}"
                path_dict["edge_list"].append(
                    {"edge": f"{subj}-{obj}", "stmts": [(href, txt)]})
            path_dict["path"] = path_string
            formatted_path_list.append(path_dict)
        return formatted_path_list

    tests = stats_json['test_round_summary']['all_test_results'][test_hash]
    return _extract_stmt_link(tests['test']),\
        tests[model_id][0], \
        tests[model_id][1]


def _new_applied_tests(model_stats_json, model_types, model_name):
    # Extract new applied tests into:
    #   list of tests (one per row)
    #       each test is a list of tuples (one tuple per column)
    #           each tuple is a (href, link_text) pair
    all_test_results = model_stats_json['test_round_summary'][
        'all_test_results']
    new_app_hashes = model_stats_json['tests_delta']['applied_hashes_delta'][
        'added']
    new_app_tests = [(th, all_test_results[th]) for th in new_app_hashes]
    return _format_table_array(new_app_tests, model_types, model_name)


def _format_table_array(tests_json, model_types, model_name):
    # tests_json needs to have the structure: [(test_hash, tests)]
    table_array = []
    for th, test in tests_json:
        new_row = [_extract_stmt_link(test['test'])]
        for mt in model_types:
            new_row.append((f'/tests/{model_name}/{mt}/{th}', test[mt][0]))

        table_array.append(new_row)
    return table_array


def _new_passed_tests(model_name, model_stats_json, current_model_types):
    new_passed_tests = []
    all_test_results = model_stats_json['test_round_summary'][
        'all_test_results']
    for mt in current_model_types:
        new_passed_hashes = model_stats_json['tests_delta'][mt][
            'passed_hashes_delta']['added']
        if not new_passed_hashes:
            continue
        mt_rows = [[('', f'New passed tests for {mt} model.')]]
        for test_hash in new_passed_hashes:
            test = all_test_results[test_hash]
            path = test[mt][1][0]['path']
            new_row = [_extract_stmt_link(test['test']),
                       (f'/tests/{model_name}/{mt}/{test_hash}', path)]
            mt_rows.append(new_row)
        new_passed_tests += mt_rows
    return new_passed_tests


@app.route('/')
@app.route('/home')
@jwt_optional
def get_home():
    user, roles = resolve_auth(dict(request.args))
    model_data = _get_model_meta_data()
    return render_template('index_template.html', model_data=model_data,
                           link_list=link_list,
                           user_email=user.email if user else "",
                           identity=user.identity() if user else None)


@app.route('/dashboard/<model>')
@jwt_optional
def get_model_dashboard(model):
    user, roles = resolve_auth(dict(request.args))
    model_meta_data = _get_model_meta_data()
    mod_link_list = [('.' + t[0], t[1]) for t in link_list]

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
        [('', 'Last Updated'), ('', last_update)],
        [('', 'Network on Ndex'),
         (f'http://www.ndexbio.org/#/network/{ndex_id}', ndex_id)]]
    model_stats = get_model_stats(model)
    all_new_tests = [(k, v) for k, v in model_stats['test_round_summary'][
        'all_test_results'].items()]
    current_model_types = [mt for mt in ALL_MODEL_TYPES if mt in
                           model_stats['test_round_summary']]
    most_supported = model_stats['model_summary']['stmts_by_evidence'][:10]
    english_by_hash = model_stats['model_summary']['english_stmts']
    top_stmts_counts = _fix_top_stmts(english_by_hash, most_supported)
    added_stmts = [[_extract_stmt_link(a)] for a in model_stats[
        'model_delta']['statements_delta']['added']]
    return render_template('model_template.html',
                           model=model,
                           model_data=model_meta_data,
                           model_stats_json=model_stats,
                           link_list=mod_link_list,
                           user_email=user.email if user else "",
                           stmts_counts=top_stmts_counts,
                           added_stmts=added_stmts,
                           model_info_contents=model_info_contents,
                           model_types=["Test", *current_model_types],
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
    model_meta_data = _get_model_meta_data()
    mod_link_list = [('.' + t[0], t[1]) for t in link_list]
    ndex_id = 'None available'
    for mid, mmd in model_meta_data:
        if mid == model:
            ndex_id = mmd['ndex']['network']
    if ndex_id == 'None available':
        logger.warning(f'No ndex ID found for {model}')
    model_stats = get_model_stats(model)
    test, test_status, path_list = _get_test_results(model_stats,
                                                     model_type,
                                                     test_hash)
    return render_template('tests_template.html',
                           link_list=mod_link_list,
                           model=model,
                           model_type=model_type,
                           all_model_types=ALL_MODEL_TYPES,
                           test_hash=test_hash,
                           model_stats_json=model_stats,
                           ndexID=ndex_id,
                           test=test,
                           test_status=test_status,
                           path_list=path_list,
                           formatted_names=FORMATTED_MODEL_NAMES)


@app.route('/query')
@jwt_optional
def get_query_page():
    user, roles = resolve_auth(dict(request.args))
    user_email = user.email if user else ""
    user_id = user.id if user else None
    model_meta_data = _get_model_meta_data()
    stmt_types = get_queryable_stmt_types()

    # user_email = 'joshua@emmaa.com'
    old_results = qm.get_registered_queries(user_email) if user_email else []

    return render_template('query_template.html', model_data=model_meta_data,
                           stmt_types=stmt_types, old_results=old_results,
                           link_list=link_list, user_email=user_email,
                           user_id=user_id, model_names=FORMATTED_MODEL_NAMES)


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
                logger.warning('User not logged in! Query will not be '
                               'registered.')
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
        logger.info('Answer to query received, responding to client.')
        res = {'result': result}

    logger.info('Result: %s' % str(res))
    return Response(json.dumps(res), mimetype='application/json')


# if __name__ == '__main__':
#     parser = argparse.ArgumentParser('Run the EMMAA dashboard service.')
#     parser.add_argument('--host', default='0.0.0.0')
#     parser.add_argument('--port', default=5000, type=int)
#     parser.add_argument('--preload', action='store_true')
#     args = parser.parse_args()

#     # TODO: make pre-loading available when running service via Gunicorn
#     if args.preload and not GLOBAL_PRELOAD:
#         # Load all the model configs
#         model_meta_data = _get_model_meta_data()
#         # Load all the model mamangers for queries
#         for model, _ in model_meta_data:
#             load_model_manager_from_s3(model)

#     print(app.url_map)  # Get all avilable urls and link them
#     app.run(host=args.host, port=args.port)
