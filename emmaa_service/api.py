import json
import argparse
import boto3
import logging
from os import path
from jinja2 import Template
from botocore.exceptions import ClientError
from flask import abort, Flask, request, Response

from indra.statements import get_all_descendants, IncreaseAmount, \
    DecreaseAmount, Activation, Inhibition, AddModification, \
    RemoveModification, get_statement_by_name, Agent

from emmaa.model import load_config_from_s3
from emmaa.answer_queries import QueryManager, load_model_manager_from_s3
from emmaa.queries import PathProperty, get_agent_from_text, GroundingError


app = Flask(__name__)
logger = logging.getLogger(__name__)


HERE = path.dirname(path.abspath(__file__))
EMMAA = path.join(HERE, path.pardir)
DASHBOARD = path.join(EMMAA, 'dashboard')


qm = QueryManager()


# Create a template object from the template file, load once
def _load_template(fname):
    template_path = path.join(DASHBOARD, fname)
    with open(template_path, 'rt') as f:
        template_str = f.read()
        template = Template(template_str)
    return template


INDEX = _load_template('index.html')
MODEL = _load_template('model.html')
QUERIES = _load_template('query.html')


def _get_models():
    s3 = boto3.client('s3')
    resp = s3.list_objects(Bucket='emmaa', Prefix='models/', Delimiter='/')
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


GLOBAL_PRELOAD = False
model_cache = {}
if GLOBAL_PRELOAD:
    # Load all the model configs
    models = _get_models()
    # Load all the model managers for queries
    for model, _ in models:
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


@app.route('/')
@app.route('/home')
def get_home():
    model_data = _get_models()
    return INDEX.render(model_data=model_data)


@app.route('/dashboard/<model>')
def get_model_dashboard(model):
    model_data = _get_models()
    return MODEL.render(model=model, model_data=model_data)


@app.route('/query')
def get_query_page():
    # TODO Should pass user specific info in the future when logged in
    model_data = _get_models()
    stmt_types = get_queryable_stmt_types()

    user_email = 'joshua@emmaa.com'
    old_results = qm.get_registered_queries(user_email)

    return QUERIES.render(model_data=model_data, stmt_types=stmt_types,
                          old_results=old_results)


@app.route('/query/submit', methods=['POST'])
def process_query():
    # Print inputs.
    logger.info('Got model query')
    logger.info("Args -----------")
    logger.info(request.args)
    logger.info("Json -----------")
    logger.info(str(request.json))
    logger.info("------------------")

    # Extract info.
    expected_query_keys = {f'{pos}Selection'
                           for pos in ['subject', 'object', 'type']}
    expceted_models = {mid for mid, _ in _get_models()}
    try:
        user_email = request.json['user']['email']
        subscribe = request.json['register']
        query_json = request.json['query']
        assert set(query_json.keys()) == expected_query_keys, \
            (f'Did not get expected query keys: got {set(query_json.keys())} '
             f'not {expected_query_keys}')
        models = set(request.json.get('models'))
        assert models < expceted_models, \
            f'Got unexpected models: {models - expceted_models}'
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
        result = qm.answer_immediate_query(
            user_email, query, models, subscribe)
        logger.info('Answer to query received, responding to client.')
        res = {'result': result}

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
        models = _get_models()
        # Load all the model mamangers for queries
        for model, _ in models:
            load_model_manager_from_s3(model)

    print(app.url_map)  # Get all avilable urls and link them
    app.run(host=args.host, port=args.port)
