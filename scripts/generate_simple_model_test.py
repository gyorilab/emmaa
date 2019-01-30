import pickle
import datetime
import yaml
import boto3
from indra.statements import *
from indra.sources import trips
from emmaa.model import EmmaaModel
from emmaa.statements import EmmaaStatement
from emmaa.model_tests import StatementCheckingTest


def generate_model(model_name):
    """Generate a simple model for end-to-end testing using natural language."""
    tp = trips.process_text('BRAF activates MAP2K1. MAP2K1 activates MAPK1.')
    indra_stmts = tp.statements
    emmaa_stmts = [EmmaaStatement(stmt, datetime.datetime.now(), 'MAPK1')
                    for stmt in indra_stmts]
    config_dict = {'ndex': {'network': 'testing'},
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
    # Upload model to S3
    model.save_to_s3()
    s3_client = boto3.client('s3')
    config_yaml = yaml.dump(config)
    s3_client.put_object(Body=config_yaml.encode('utf8'),
                         Key='models/%s/config.yaml' % model_name,
                         Bucket='emmaa')
    # Upload test to S3
    test_key = 'tests/simple_model_test.pkl'
    s3_client.put_object(Body=pickle.dumps(test), Key=test_key, Bucket='emmaa')
