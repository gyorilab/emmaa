import datetime
import json
import os
import pickle
import re

from moto import mock_s3

from emmaa.priors import SearchTerm
from emmaa.statements import EmmaaStatement
from emmaa.tests.test_model import indra_stmts
from emmaa.tests.test_stats import previous_results, new_results, \
    previous_test_stats, previous_model_stats
from emmaa.util import make_date_str, RE_DATETIMEFORMAT, RE_DATEFORMAT


TEST_BUCKET_NAME = 'test_bucket'


@mock_s3
def setup_bucket(
        add_model=False, add_mm=False, add_tests=False,
        add_results=False, add_model_stats=False, add_test_stats=False):
    """
    This function creates a new (local) bucket mocking S3 bucket at each call.
    Then all calls to S3 are calling this bucket instead of real S3 bucket.
    Depending on the test we might or might not need the bucket to contain
    different files. For faster computation, only required files for the test
    are generated and stored in the bucket. Files can be added by setting
    corresponding arguments to True when calling this function.
    """
    # Local imports are recommended when using moto
    from emmaa.util import get_s3_client
    from emmaa.model import EmmaaModel, save_config_to_s3
    from emmaa.model_tests import ModelManager, save_model_manager_to_s3, \
        StatementCheckingTest
    # Create a mock s3 bucket
    client = get_s3_client()
    bucket = client.create_bucket(Bucket=TEST_BUCKET_NAME, ACL='public-read')
    date_str = make_date_str()
    if add_model:
        # Put config and model files into empty bucket
        config_dict = {
            'ndex': {'network': 'a08479d1-24ce-11e9-bb6a-0ac135e8bacf'},
            'search_terms': [{'db_refs': {'HGNC': '20974'}, 'name': 'MAPK1',
                              'search_term': 'MAPK1', 'type': 'gene'}]}
        save_config_to_s3('test', config_dict, bucket=TEST_BUCKET_NAME)
        st = SearchTerm('gene', 'MAP2K1', db_refs={}, search_term='MAP2K1')
        emmaa_stmts = [EmmaaStatement(stmt, datetime.datetime.now(), [st])
                       for stmt in indra_stmts]
        emmaa_model = EmmaaModel('test', config_dict)
        emmaa_model.add_statements(emmaa_stmts)
        emmaa_model.save_to_s3(bucket=TEST_BUCKET_NAME)
    if add_mm:
        # Add a ModelManager to bucket
        mm = ModelManager(emmaa_model)
        mm.date_str = date_str
        save_model_manager_to_s3('test', mm, bucket=TEST_BUCKET_NAME)
    if add_tests:
        tests = [StatementCheckingTest(
            Activation(Agent('BRAF'), Agent('MAPK1')))]
        client.put_object(Body=pickle.dumps(tests), Bucket=TEST_BUCKET_NAME,
                          Key=f'tests/simple_tests.pkl')
    if add_results:
        client.put_object(
            Body=json.dumps(previous_results, indent=1),
            Bucket=TEST_BUCKET_NAME,
            Key=f'results/test/results_simple_tests_{date_str}.json')
    if add_model_stats:
        client.put_object(
            Body=json.dumps(previous_model_stats, indent=1),
            Bucket=TEST_BUCKET_NAME,
            Key=f'model_stats/test/model_stats_{date_str}.json')
    if add_test_stats:
        client.put_object(
            Body=json.dumps(previous_test_stats, indent=1),
            Bucket=TEST_BUCKET_NAME,
            Key=f'stats/test/test_stats_simple_tests_{date_str}.json')


@mock_s3
