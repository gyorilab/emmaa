import datetime
import json
import os
import pickle
import re

from moto import mock_s3

from indra.statements import Activation, Agent
from emmaa.priors import SearchTerm
from emmaa.statements import EmmaaStatement
from emmaa.tests.test_model import create_model
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
    emmaa_model = None
    if add_model:
        # Put config and model files into empty bucket
        config_dict = {
            'ndex': {'network': 'a08479d1-24ce-11e9-bb6a-0ac135e8bacf'},
            'search_terms': [{'db_refs': {'HGNC': '20974'}, 'name': 'MAPK1',
                              'search_term': 'MAPK1', 'type': 'gene'}]}
        save_config_to_s3('test', config_dict, bucket=TEST_BUCKET_NAME)
        emmaa_model = create_model()
        emmaa_model.save_to_s3(bucket=TEST_BUCKET_NAME)
    if add_mm:
        # Add a ModelManager to bucket
        if not emmaa_model:
            emmaa_model = create_model()
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
    return client

@mock_s3
def test_save_load_config():
    # Local imports are recommended when using moto
    from emmaa.model import save_config_to_s3, load_config_from_s3
    setup_bucket()
    config = {'test': 'This is test config'}
    save_config_to_s3('test', config, bucket=TEST_BUCKET_NAME)
    read_config = load_config_from_s3('test', bucket=TEST_BUCKET_NAME)
    assert config == read_config


@mock_s3
def test_load_model():
    # Local imports are recommended when using moto
    from emmaa.model import EmmaaModel
    setup_bucket(add_model=True)
    em = EmmaaModel.load_from_s3('test', bucket='test_bucket')
    assert isinstance(em, EmmaaModel)
    assert len(em.stmts) == 2, len(em.stmts)
    assert em.name == 'test'


@mock_s3
def test_last_updated():
    # Local imports are recommended when using moto
    from emmaa.model import last_updated_date
    setup_bucket(add_model=True, add_results=True, add_model_stats=True,
                 add_test_stats=True)
    # Test for different file types
    key_str = last_updated_date(
        'test', 'model', 'datetime', extension='.pkl',
        bucket=TEST_BUCKET_NAME)
    assert key_str
    assert re.search(RE_DATETIMEFORMAT, key_str).group()
    key_str = last_updated_date(
        'test', 'test_results', 'datetime', 'simple_tests',
        extension='.json', bucket=TEST_BUCKET_NAME)
    assert key_str
    assert re.search(RE_DATETIMEFORMAT, key_str).group()
    key_str = last_updated_date(
        'test', 'test_stats', 'datetime', 'simple_tests', 
        extension='.json', bucket=TEST_BUCKET_NAME)
    assert key_str
    assert re.search(RE_DATETIMEFORMAT, key_str).group()
    key_str = last_updated_date(
        'test', 'model_stats', 'datetime',
        extension='.json', bucket=TEST_BUCKET_NAME)
    assert key_str
    assert re.search(RE_DATETIMEFORMAT, key_str).group()
    # Test for different date format
    key_str = last_updated_date(
        'test', 'model', 'date', extension='.pkl', bucket=TEST_BUCKET_NAME)
    assert key_str
    assert re.search(RE_DATEFORMAT, key_str).group()
    # Test with wrong extension
    key_str = last_updated_date(
        'test', 'test_stats', 'datetime', 'simple_tests', extension='.pkl',
        bucket=TEST_BUCKET_NAME)
    assert not key_str


@mock_s3
def test_get_model_statistics():
    # Local imports are recommended when using moto
    from emmaa.model import get_model_stats
    client = setup_bucket(add_model_stats=True, add_test_stats=True)
    # Get latest model stats
    model_stats = get_model_stats('test', 'model', bucket=TEST_BUCKET_NAME)
    assert isinstance(model_stats, dict)
    # Get latest test stats
    test_stats = get_model_stats('test', 'test', 'simple_tests',
                                 bucket=TEST_BUCKET_NAME)
    assert isinstance(test_stats, dict)
    # Try with a different date
    new_stats = get_model_stats(
        'test', 'model', date='2020-01-01', bucket=TEST_BUCKET_NAME)
    assert not new_stats
    # Put missing file and try again
    client.put_object(
        Body=json.dumps(previous_model_stats, indent=1),
        Bucket=TEST_BUCKET_NAME,
        Key=f'model_stats/test/model_stats_2020-01-01-00-00-00.json')
    new_stats = get_model_stats(
        'test', 'model', date='2020-01-01', bucket=TEST_BUCKET_NAME)
    assert new_stats
    assert isinstance(new_stats, dict)


@mock_s3
def test_load_tests_from_s3():
    # Local imports are recommended when using moto
    from emmaa.model_tests import load_tests_from_s3, StatementCheckingTest
    setup_bucket(add_tests=True)
    tests = load_tests_from_s3('simple_tests', bucket=TEST_BUCKET_NAME)
    assert isinstance(tests, list)
    assert len(tests) == 1
    test = tests[0]
    assert isinstance(test, StatementCheckingTest)


@mock_s3
def test_run_model_tests_from_s3():
    # Local imports are recommended when using moto
    from emmaa.model_tests import run_model_tests_from_s3, ModelManager
    from emmaa.model import last_updated_date
    setup_bucket(add_tests=True, add_mm=True)
    # There should not be any results
    assert not last_updated_date('test', 'test_results', tests='simple_tests',
                                 extension='.json', bucket=TEST_BUCKET_NAME)
    mm = run_model_tests_from_s3('test', 'simple_tests', upload_results=True,
                                 bucket=TEST_BUCKET_NAME)
    assert isinstance(mm, ModelManager)
    # Results are saved now
    assert last_updated_date('test', 'test_results', tests='simple_tests',
                             extension='.json', bucket=TEST_BUCKET_NAME)
