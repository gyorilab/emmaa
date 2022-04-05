import pickle
import datetime
import json
import boto3
from indra.statements import *
from indra.sources import trips
from indra.assemblers.cx import CxAssembler
from emmaa.model import EmmaaModel
from emmaa.statements import EmmaaStatement
from emmaa.model_tests import StatementCheckingTest


def generate_model(model_name):
    """Generate a simple model for end-to-end testing using natural language."""
    tp = trips.process_text('BRAF activates MAP2K1. '
                            'Active MAP2K1 activates MAPK1.')
    indra_stmts = tp.statements
    emmaa_stmts = [EmmaaStatement(stmt, datetime.datetime.now(), 'MAPK1',
                                  {'internal': True})
                   for stmt in indra_stmts]
    # Create a CXAssembled model, upload to NDEx and retrieve key
    #cxa = CxAssembler(indra_stmts)
    #cxa.make_model()
    #ndex_id = cxa.upload_model(private=False)
    config_dict = {'ndex': {'network': 'a08479d1-24ce-11e9-bb6a-0ac135e8bacf'},
                   'search_terms': [{'db_refs': {'HGNC': '20974'},
                                     'name': 'MAPK1',
                                     'search_term': 'MAPK1',
                                     'type': 'gene'}]}
    emmaa_model = EmmaaModel(model_name, config_dict)
    emmaa_model.add_statements(emmaa_stmts)
    return emmaa_model, config_dict


def generate_test():
    """Generate a simple test for the model."""
    tp = trips.process_text('BRAF activates MAPK1.')
    stmt = tp.statements[0]
    return [StatementCheckingTest(stmt)]


if __name__ == '__main__':
    model_name = 'test'
    model, config = generate_model(model_name)
    test = generate_test()
    # Upload model to S3 as json
    model.save_to_s3()
    s3_client = boto3.client('s3')
    config_json = json.dumps(config, indent=1)
    s3_client.put_object(Body=config_json.encode('utf8'),
                         Key='models/%s/config.json' % model_name,
                         Bucket='emmaa')
    # Upload test to S3
    test_key = 'tests/simple_model_test.pkl'
    s3_client.put_object(Body=pickle.dumps(test), Key=test_key, Bucket='emmaa')
