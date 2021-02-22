import unittest

from moto import mock_s3
from emmaa.util import make_date_str
from emmaa.tests.test_s3 import setup_bucket, TEST_BUCKET_NAME
from emmaa.queries import PathProperty, DynamicProperty


@mock_s3
def test_api_load_from_s3():
    from emmaa_service.api import is_available, get_latest_available_date, \
        _get_test_corpora, _get_model_meta_data, get_model_config
    from emmaa.model import last_updated_date
    client = setup_bucket(add_model=True, add_model_stats=True,
                          add_test_stats=True)
    today = make_date_str()[:10]
    other_day = '2020-01-01'
    assert is_available('test', 'simple_tests', today, TEST_BUCKET_NAME)
    assert not is_available(
        'test', 'large_corpus_tests', today, TEST_BUCKET_NAME)
    assert not is_available(
        'test', 'simple_tests', other_day, TEST_BUCKET_NAME)
    assert get_latest_available_date(
        'test', 'simple_tests', bucket=TEST_BUCKET_NAME) == today
    config = get_model_config('test', TEST_BUCKET_NAME)
    assert config
    test_corpora = _get_test_corpora('test', TEST_BUCKET_NAME)
    assert test_corpora == {'simple_tests'}
    metadata = _get_model_meta_data(bucket=TEST_BUCKET_NAME)
    assert len(metadata) == 1
    assert len(metadata[0]) == 2
    assert metadata[0][0] == 'test'
    assert metadata[0][1] == config


def test_make_query():
    from emmaa_service.api import _make_query
    query, tab = _make_query({
        'typeSelection': 'Activation',
        'subjectSelection': 'BRAF',
        'objectSelection': 'MAPK1'})
    assert isinstance(query, PathProperty)
    assert tab == 'static'
    query, tab = _make_query({
        'agentSelection': 'phosphorylated MAP2K1',
        'valueSelection': 'low',
        'patternSelection': 'always_value'})
    assert isinstance(query, DynamicProperty)
    assert tab == 'dynamic'


class EmmaaApiTest(unittest.TestCase):

    def setUp(self):
        from .api import app
        app.testing = True
        self.app = app.test_client()

    def test_query_endpoint(self):
        """Test if we can submit a simple model query

        NOTE: only tests that the query was received by the API and that it
        was properly formatted.
        """

        test_query = {'user': {'email': 'joshua@emmaa.com',
                               'name': 'joshua',
                               'slack_id': '123456abcdef'},
                      'models': ['aml', 'luad'],
                      'query': {'objectSelection': 'ERK',
                                'subjectSelection': 'BRAF',
                                'typeSelection': 'activation'},
                      'register': False,
                      'test': 'true'}

        resp = self.app.post('/query/submit', json=test_query)

        assert resp.status_code == 200

    def test_query(self):
        """Test querying a model"""

        test_query = {'user': {'email': 'joshua@emmaa.com',
                                   'name': 'joshua',
                                   'slack_id': '123456abcdef'},
                          'models': ['rasmodel'],
                          'query': {'objectSelection': 'AKT1',
                                    'subjectSelection': 'PIK3CA',
                                    'typeSelection': 'activation'},
                          'register': False}

        resp = self.app.post('/query/submit', json=test_query)

        assert resp.status_code == 200
