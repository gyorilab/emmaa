import json
from os import path

import boto3
import logging
from botocore.exceptions import ClientError
from flask import abort, Flask, request, Response

from emmaa.model import load_config_from_s3
from indra.statements import get_all_descendants, Statement
from jinja2 import Template

from emmaa.answer_queries import answer_immediate_query

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
        model_id = pref['Prefix'].split('/')[1]
        try:
            config_json = load_config_from_s3(model_id)
        except ClientError:
            logger.warning(f"Model {model_id} has no metadata. Skipping...")
            continue
        if 'human_readable_name' not in config_json.keys():
            logger.warning(f"Model {model_id} has readable name. Skipping...")
            continue
        model_data.append((model_id, config_json))
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
    stmt_types = [s.__class__.__name__ for s in get_all_descendants(Statement)]
    return QUERIES.render(model_data=model_data, stmt_types=stmt_types)


@app.route('/query/submit', methods=['POST'])
def process_query():
    logger.info('Got model query')
    print("Args -----------")
    print(request.args)
    print("Json -----------")
    print(str(request.json))
    print("------------------")
    models = []
    subj = ''
    obj = ''
    stmt_type = ''
    user_info = request.json.get('user')
    register = 'true' == request.json.get('register') if \
        request.args.get('register') else False
    is_test = 'test' in request.json or 'test' == request.json.get('tag')

    if is_test:
        logger.info('Test passed')
        res = {'result': 'test passed', 'ref': None}

    else:
        if request.json.get('query'):
            models = request.json.get('query').get('models')
            subj = request.json.get('query').get('subjectSelection')
            obj = request.json.get('query').get('objectSelection')
            stmt_type = request.json.get('query').get('typeSelection')

        if all([models, subj, obj, stmt_type]):
            query_dict = request.json.copy()
            assert 'test' not in request.json

            # submit to emmaa query db
            logger.info('Query submitted')
            result = answer_immediate_query(query_dict)
            logger.info('Answer to query received, responding to client.')
            res = {'result': result}
        else:
            # send error
            logger.info('Invalid query')
            abort(Response('Invalid query', 400))

    logger.info('Result: %s' % str(res))
    return Response(json.dumps(res), mimetype='application/json')


if __name__ == '__main__':
    print(app.url_map)  # Get all avilable urls and link them
    app.run()
