import datetime
import json
import os
import pickle
import re
import time
from moto import mock_s3
from nose.plugins.attrib import attr
from nose.tools import with_setup

from indra.statements import Activation, Agent
from emmaa.priors import SearchTerm
from emmaa.statements import EmmaaStatement
from emmaa.tests.test_model import create_model
from emmaa.tests.test_stats import previous_results, new_results, \
    previous_test_stats, previous_model_stats
from emmaa.tests.test_answer_queries import query_object
from emmaa.util import make_date_str, RE_DATETIMEFORMAT, RE_DATEFORMAT
from emmaa.tests.db_setup import _get_test_db, setup_function, \
    teardown_function

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
                              'search_term': 'MAPK1', 'type': 'gene'}],
            'test': {'test_corpus': 'simple_tests',
                     'default_test_corpus': 'simple_tests'},
            'human_readable_name': 'Test Model',
            'assembly': [
                {'function': 'filter_no_hypothesis'},
                {'function': 'map_grounding'},
                {'function': 'filter_grounded_only'},
                {'function': 'filter_human_only'},
                {'function': 'map_sequence'},
                {'function': 'run_preassembly', 'kwargs': {
                    'return_toplevel': False}},
                {'function': 'filter_top_level'}]
            }
        save_config_to_s3('test', config_dict, bucket=TEST_BUCKET_NAME)
        emmaa_model = create_model()
        emmaa_model.save_to_s3(bucket=TEST_BUCKET_NAME)
    if add_mm:
        # Add a ModelManager to bucket
        if not emmaa_model:
            emmaa_model = create_model()
        mm = ModelManager(emmaa_model)
        mm.date_str = date_str
        mm.save_assembled_statements(bucket=TEST_BUCKET_NAME)
        save_model_manager_to_s3('test', mm, bucket=TEST_BUCKET_NAME)
    if add_tests:
        tests = [StatementCheckingTest(
            Activation(Agent('BRAF'), Agent('MAPK1')))]
        test_dict = {
            'test_data': {'description': 'Tests for functionality testing'},
            'tests': tests}
        client.put_object(Body=pickle.dumps(test_dict),
                          Bucket=TEST_BUCKET_NAME,
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
    client = setup_bucket()
    config = {'test': 'This is test config'}
    save_config_to_s3('test', config, bucket=TEST_BUCKET_NAME)
    read_config = load_config_from_s3('test', bucket=TEST_BUCKET_NAME)
    assert config == read_config


@mock_s3
def test_load_model():
    # Local imports are recommended when using moto
    from emmaa.model import EmmaaModel
    client = setup_bucket(add_model=True)
    em = EmmaaModel.load_from_s3('test', bucket='test_bucket')
    assert isinstance(em, EmmaaModel)
    assert len(em.stmts) == 2, len(em.stmts)
    assert em.name == 'test'


@mock_s3
def test_last_updated():
    # Local imports are recommended when using moto
    from emmaa.model import last_updated_date
    client = setup_bucket(add_model=True, add_results=True,
                          add_model_stats=True, add_test_stats=True)
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
    client = setup_bucket(add_model=True, add_model_stats=True, add_test_stats=True)
    # Get latest model stats
    model_stats, key = get_model_stats(
        'test', 'model', bucket=TEST_BUCKET_NAME)
    assert isinstance(model_stats, dict)
    assert key.startswith('model_stats/test/model_stats_')
    # Get latest test stats
    test_stats, key = get_model_stats('test', 'test', 'simple_tests',
                                      bucket=TEST_BUCKET_NAME)
    assert isinstance(test_stats, dict)
    assert key.startswith('stats/test/test_stats_')
    # Try with a different date
    new_stats, key = get_model_stats(
        'test', 'model', date='2020-01-01', bucket=TEST_BUCKET_NAME)
    assert not new_stats
    assert not key
    # Put missing file and try again
    client.put_object(
        Body=json.dumps(previous_model_stats, indent=1),
        Bucket=TEST_BUCKET_NAME,
        Key=f'model_stats/test/model_stats_2020-01-01-00-00-00.json')
    new_stats, key = get_model_stats(
        'test', 'model', date='2020-01-01', bucket=TEST_BUCKET_NAME)
    assert new_stats
    assert isinstance(new_stats, dict)
    assert key == 'model_stats/test/model_stats_2020-01-01-00-00-00.json'


@mock_s3
def test_get_assembled_stmts():
    # Local imports are recommended when using moto
    from emmaa.model import get_assembled_statements
    client = setup_bucket(add_mm=True)
    stmts, fkey = get_assembled_statements('test', bucket=TEST_BUCKET_NAME)
    assert len(stmts) == 2, stmts
    assert all([isinstance(stmt, Activation) for stmt in stmts])


@mock_s3
def test_load_tests_from_s3():
    # Local imports are recommended when using moto
    from emmaa.model_tests import load_tests_from_s3, StatementCheckingTest
    client = setup_bucket(add_tests=True)
    test_dict, _ = load_tests_from_s3('simple_tests', bucket=TEST_BUCKET_NAME)
    assert isinstance(test_dict, dict)
    tests = test_dict['tests']
    assert isinstance(tests, list)
    assert len(tests) == 1
    test = tests[0]
    assert isinstance(test, StatementCheckingTest)
    assert isinstance(test_dict['test_data'], dict)
    assert isinstance(test_dict['test_data']['description'], str)


@mock_s3
def test_run_model_tests_from_s3():
    # Local imports are recommended when using moto
    from emmaa.model_tests import run_model_tests_from_s3, ModelManager
    from emmaa.model import last_updated_date
    client = setup_bucket(add_tests=True, add_mm=True)
    # There should not be any results
    assert not last_updated_date('test', 'test_results', tests='simple_tests',
                                 extension='.json', bucket=TEST_BUCKET_NAME)
    mm = run_model_tests_from_s3('test', 'simple_tests', upload_results=True,
                                 bucket=TEST_BUCKET_NAME)
    assert isinstance(mm, ModelManager)
    # Results are saved now
    assert last_updated_date('test', 'test_results', tests='simple_tests',
                             extension='.json', bucket=TEST_BUCKET_NAME)


@mock_s3
def test_save_load_update_model_manager():
    # Local imports are recommended when using moto
    from emmaa.model_tests import ModelManager, save_model_manager_to_s3, \
        load_model_manager_from_s3, update_model_manager_on_s3
    from emmaa.util import find_number_of_files_on_s3, \
        sort_s3_files_by_date_str
    client = setup_bucket(add_model=True)
    # Should be None if no model manager
    assert find_number_of_files_on_s3(
        TEST_BUCKET_NAME, 'results/test/model_manager_', '.pkl') == 0
    loaded_mm = load_model_manager_from_s3(model_name='test',
                                           bucket=TEST_BUCKET_NAME)
    assert loaded_mm is None
    # Save a model manager and load it back
    model = create_model()
    mm = ModelManager(model)
    save_model_manager_to_s3('test', mm, bucket=TEST_BUCKET_NAME)
    loaded_mm = load_model_manager_from_s3(model_name='test',
                                           bucket=TEST_BUCKET_NAME)
    assert loaded_mm
    assert find_number_of_files_on_s3(
        TEST_BUCKET_NAME, 'results/test/model_manager_', '.pkl') == 1
    # Update should create a new file if there's at least one second difference
    time.sleep(1)
    update_model_manager_on_s3('test', TEST_BUCKET_NAME)
    assert find_number_of_files_on_s3(
        TEST_BUCKET_NAME, 'results/test/model_manager_', '.pkl') == 2

@mock_s3
def test_model_to_tests():
    # Local imports are recommended when using moto
    from emmaa.model_tests import model_to_tests, load_tests_from_s3, \
        StatementCheckingTest
    client = setup_bucket(add_model=True)
    test_dict = model_to_tests('test', bucket=TEST_BUCKET_NAME)
    assert isinstance(test_dict, dict)
    assert 'test_data' in test_dict
    assert 'tests' in test_dict
    tests = test_dict['tests']
    assert len(tests) == 2
    assert isinstance(tests[0], StatementCheckingTest)
    loaded_tests, _ = load_tests_from_s3('test_tests', bucket=TEST_BUCKET_NAME)
    assert loaded_tests
    assert isinstance(loaded_tests, dict)
    assert 'test_data' in loaded_tests
    assert 'tests' in loaded_tests


@attr('notravis', 'nonpublic')
@mock_s3
def test_generate_stats_on_s3():
    # Local imports are recommended when using moto
    from emmaa.analyze_tests_results import generate_stats_on_s3
    from emmaa.util import find_number_of_files_on_s3, make_date_str
    from emmaa.model_tests import update_model_manager_on_s3
    # Try with only one set of results first (as for new model/test)
    client = setup_bucket(add_results=True, add_mm=True, add_model=True)
    msg = generate_stats_on_s3('test', 'model', upload_stats=True,
                               bucket=TEST_BUCKET_NAME)
    assert msg.latest_round
    assert not msg.previous_round
    assert not msg.previous_json_stats
    assert find_number_of_files_on_s3(
        TEST_BUCKET_NAME, 'model_stats/test/model_stats_') == 1
    tsg = generate_stats_on_s3('test', 'tests', 'simple_tests',
                               upload_stats=True, bucket=TEST_BUCKET_NAME)
    assert tsg.latest_round
    assert not tsg.previous_round
    assert not tsg.previous_json_stats
    assert find_number_of_files_on_s3(
        TEST_BUCKET_NAME, 'stats/test/test_stats_') == 1
    # Now add new results and new mm
    time.sleep(1)
    update_model_manager_on_s3('test', TEST_BUCKET_NAME)
    client.put_object(
        Body=json.dumps(previous_results, indent=1),
        Bucket=TEST_BUCKET_NAME,
        Key=f'results/test/results_simple_tests_{make_date_str()}.json')
    msg = generate_stats_on_s3('test', 'model', upload_stats=True,
                               bucket=TEST_BUCKET_NAME)
    assert msg.latest_round
    assert msg.previous_round
    assert msg.previous_json_stats
    assert find_number_of_files_on_s3(
        TEST_BUCKET_NAME, 'model_stats/test/model_stats_') == 2
    tsg = generate_stats_on_s3('test', 'tests', 'simple_tests',
                               upload_stats=True, bucket=TEST_BUCKET_NAME)
    assert tsg.latest_round
    assert tsg.previous_round
    assert tsg.previous_json_stats
    assert find_number_of_files_on_s3(
        TEST_BUCKET_NAME, 'stats/test/test_stats_') == 2


@with_setup(setup_function, teardown_function)
@mock_s3
def test_answer_queries_from_s3():
    # Local imports are recommended when using moto
    from emmaa.answer_queries import answer_queries_from_s3
    db = _get_test_db()
    client = setup_bucket(add_mm=True)
    db.put_queries('tester@test.com', 1, query_object, ['test'],
                   subscribe=True)
    answer_queries_from_s3('test', db=db, bucket=TEST_BUCKET_NAME)
    results = db.get_results('tester@test.com', latest_order=1)
    # Each model type has its own result
    assert len(results) == 4, len(results)


@mock_s3
def test_util_find_on_s3_functions():
    # Local imports are recommended when using moto
    from emmaa.util import sort_s3_files_by_date_str, find_latest_s3_file, \
        find_nth_latest_s3_file, find_number_of_files_on_s3
    # Bucket has mm (pkl) and results (json) files, both in results folder
    client = setup_bucket(add_mm=True, add_results=True)
    # Get both
    files = sort_s3_files_by_date_str(TEST_BUCKET_NAME, 'results/test/')
    assert len(files) == 2
    # Specific extension
    files = sort_s3_files_by_date_str(TEST_BUCKET_NAME, 'results/test/',
                                     '.json')
    assert len(files) == 1
    # Longer prefix
    files = sort_s3_files_by_date_str(TEST_BUCKET_NAME,
                                      'results/test/results_')
    assert len(files) == 1
    assert find_latest_s3_file(TEST_BUCKET_NAME, 'results/test/results_')
    assert not find_nth_latest_s3_file(
        1, TEST_BUCKET_NAME, 'results/test/results_')
    assert find_nth_latest_s3_file(1, TEST_BUCKET_NAME, 'results/test/')
    assert find_number_of_files_on_s3(TEST_BUCKET_NAME, 'results/test/') == 2
    assert find_number_of_files_on_s3(
        TEST_BUCKET_NAME, 'results/test/results_') == 1
    assert find_number_of_files_on_s3(
        TEST_BUCKET_NAME, 'results/test/', '.json') == 1
