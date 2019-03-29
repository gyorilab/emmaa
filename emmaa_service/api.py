import json
from os import path

import boto3
import logging
from botocore.exceptions import ClientError
from flask import abort, Flask, request, Response

from emmaa.db import get_db
from emmaa.model import load_config_from_s3
from indra.statements import get_all_descendants, Statement
from jinja2 import Template

from emmaa.answer_queries import answer_immediate_query, \
    get_registered_queries, GroundingError

app = Flask(__name__)
logger = logging.getLogger(__name__)


HERE = path.dirname(path.abspath(__file__))
EMMAA = path.join(HERE, path.pardir)
DASHBOARD = path.join(EMMAA, 'dashboard')


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
        try:
            config_json = load_config_from_s3(model)
        except ClientError:
            logger.warning(f"Model {model} has no metadata. Skipping...")
            continue
        if 'human_readable_name' not in config_json.keys():
            logger.warning(f"Model {model} has no readable name. Skipping...")
            continue
        model_data.append((model, config_json))
    return model_data


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
    stmt_types = sorted([s.__name__ for s in get_all_descendants(Statement)])

    user_email = 'joshua@emmaa.com'
    old_results = get_registered_queries(user_email)

    return QUERIES.render(model_data=model_data, stmt_types=stmt_types,
                          old_results=old_results)


@app.route('/query/submit', methods=['POST'])
def process_query():
    # Print inputs.
    logger.info('Got model query')
    print("Args -----------")
    print(request.args)
    print("Json -----------")
    print(str(request.json))
    print("------------------")

    # Extract info.
    expected_query_keys = {f'{pos}Selection'
                           for pos in ['subject', 'object', 'type']}
    expceted_models = {mid for mid, _ in _get_models()}
    try:
        user_email = request.json['user']['email']
        subscribe = request.json.get('register') == 'true' if \
            request.args.get('register') else False
        query_json = request.json['query']
        assert set(query_json.keys()) == expected_query_keys, \
            (f'Did not get expected query keys: got {set(query_json.keys())} '
             f'not {expected_query_keys}')
        models = set(request.json.get('models'))
        assert models < expceted_models, \
            f'Got unexpected models: {models - expceted_models}'
    except (KeyError, AssertionError) as e:
        logger.error("Invalid query:" + e)
        abort(Response(f'Invalid request: {str(e)}', 400))

    is_test = 'test' in request.json or 'test' == request.json.get('tag')

    if is_test:
        logger.info('Test passed')
        res = {'result': 'test passed', 'ref': None}

    else:
        logger.info('Query submitted')
        try:
            result = answer_immediate_query(
                user_email, query_json, models, subscribe)
        except GroundingError as e:
            db.error("Invalid grounding.")
            abort(Response(f'Invalid entity: {str(e)}', 400))
        logger.info('Answer to query received, responding to client.')
        res = {'result': result}

    logger.info('Result: %s' % str(res))
    return Response(json.dumps(res), mimetype='application/json')


if __name__ == '__main__':
    print(app.url_map)  # Get all avilable urls and link them
    app.run()
