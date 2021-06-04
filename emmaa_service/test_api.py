import unittest
import json
from datetime import datetime
from moto import mock_s3
from emmaa.util import make_date_str, strip_out_date
from emmaa.tests.test_s3 import setup_bucket, TEST_BUCKET_NAME
from emmaa.queries import PathProperty, DynamicProperty, OpenSearchQuery, \
    SimpleInterventionProperty
from indra.statements.io import stmts_from_json


@mock_s3
def test_api_load_from_s3():
    from emmaa_service.api import is_available, get_latest_available_date, \
        _get_test_corpora, _get_model_meta_data, get_model_config
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
        'queryType': 'static',
        'typeSelection': 'Activation',
        'subjectSelection': 'BRAF',
        'objectSelection': 'MAPK1'})
    assert isinstance(query, PathProperty)
    assert tab == 'static'
    query, tab = _make_query({
        'queryType': 'dynamic',
        'agentSelection': 'phosphorylated MAP2K1',
        'valueSelection': 'low',
        'patternSelection': 'always_value'})
    assert isinstance(query, DynamicProperty)
    assert tab == 'dynamic'
    query, tab = _make_query({
        'queryType': 'intervention',
        'typeSelection': 'Activation',
        'subjectSelection': 'BRAF',
        'objectSelection': 'MAPK1'})
    assert isinstance(query, SimpleInterventionProperty)
    assert tab == 'intervention'
    query, tab = _make_query({
        'queryType': 'open',
        'stmtTypeSelection': 'Inhibition',
        'openAgentSelection': 'MAPK1',
        'roleSelection': 'object',
        'nsSelection': ['small molecules']
    })
    assert isinstance(query, OpenSearchQuery)
    assert tab == 'open'


class EmmaaApiTest(unittest.TestCase):

    def setUp(self):
        from .api import app
        app.testing = True
        self.app = app.test_client()

    def call_api(self, method, route, *args, **kwargs):
        req_meth = getattr(self.app, method)
        start = datetime.now()
        print("Submitting request to '%s' at %s." % ('/' + route, start))
        print("\targs:", args)
        print("\tkwargs:", kwargs)
        res = req_meth(route, *args, **kwargs)
        end = datetime.now()
        print("Got result with %s at %s after %s seconds."
              % (res.status_code, end, (end-start).total_seconds()))
        if res.status_code != 200:
            raise ValueError(res.status_code)
        return json.loads(res.get_data())

    def test_query_endpoint(self):
        """Test if we can submit a simple model query

        NOTE: only tests that the query was received by the API and that it
        was properly formatted.
        """

        test_query = {'user': {'email': 'joshua@emmaa.com',
                               'name': 'joshua',
                               'slack_id': '123456abcdef'},
                      'models': ['aml', 'luad'],
                      'query': {'queryType': 'static',
                                'objectSelection': 'ERK',
                                'subjectSelection': 'BRAF',
                                'typeSelection': 'activation'},
                      'register': False,
                      'test': 'true'}

        rj = self.call_api('post', 'query/submit', json=test_query)
        assert rj

    def test_get_statements(self):
        rj = self.call_api('get', 'latest/statements/marm_model')
        assert rj
        set(rj.keys()) == {'statements', 'link'}
        assert len(rj['statements']) > 20
        assert stmts_from_json(rj['statements'])

    def test_statements_url(self):
        rj = self.call_api('get', 'latest/statements_url/marm_model')
        assert rj
        set(rj.keys()) == {'link'}
        key = rj['link'].split('/')[-1]
        assert not strip_out_date(key)
        dated_rj = self.call_api(
            'get', 'latest/statements_url/marm_model?dated=true')
        key = dated_rj['link'].split('/')[-1]
        assert strip_out_date(key)

    def test_stats_date(self):
        rj = self.call_api('get', 'latest/stats_date?model=marm_model')
        assert rj
        assert set(rj.keys()) == {'model', 'test_corpus', 'date'}
        assert len(rj['date']) == 19, len(rj['date'])
        rj = self.call_api(
            'get', 'latest/stats_date?model=marm_model&date_format=date')
        assert rj
        assert set(rj.keys()) == {'model', 'test_corpus', 'date'}
        assert len(rj['date']) == 10, len(rj['date'])

    def test_curations(self):
        rj = self.call_api('get', 'latest/curated_statements/marm_model')
        assert rj
        assert set(rj.keys()) == {'correct', 'incorrect', 'partial'}

    def test_get_models(self):
        rj = self.call_api('get', 'metadata/models')
        assert rj
        assert set(rj.keys()) == {'models'}
        assert len(rj['models']) > 15

    def test_model_info(self):
        rj = self.call_api('get', 'metadata/model_info/marm_model')
        assert rj
        assert 'name' in rj
        assert 'human_readable_name' in rj

    def test_test_corpora(self):
        rj = self.call_api('get', 'metadata/test_corpora/marm_model')
        assert rj
        assert set(rj.keys()) == {'test_corpora'}
        assert isinstance(rj['test_corpora'], list)

    def test_test_info(self):
        rj = self.call_api('get', 'metadata/tests_info/large_corpus_tests')
        assert rj
        assert 'name' in rj

    def test_entity_info(self):
        rj = self.call_api(
            'get', 'metadata/entity_info/marm_model?namespace=HGNC&id=1097')
        assert rj
        assert 'url' in rj
        assert rj['url'] == 'https://identifiers.org/hgnc:1097'

    def test_source_target_path(self):
        qj = {
            "model": "rasmodel",
            "source": {
                "type": "Agent",
                "name": "EGFR",
                "db_refs": {"HGNC": "3236"}
            },
            "target": {
                "type": "Agent",
                "name": "AKT1",
                "db_refs": {"HGNC": "391"}
            },
            "stmt_type": "Activation"
            }
        rj = self.call_api('post', 'query/source_target_path', json=qj)
        assert rj
        assert set(rj.keys()) == {'pysb', 'pybel', 'signed_graph',
                                  'unsigned_graph'}

    def test_up_downstream_path(self):
        qj = {
            "model": "rasmodel",
            "entity": {
                "type": "Agent",
                "name": "AKT1",
                "db_refs": {"HGNC": "391"}
            },
            "entity_role": "object",
            "stmt_type": "Activation",
            "terminal_ns": ["HGNC", "UP", "FPLX"]
            }
        rj = self.call_api('post', 'query/up_down_stream_path', json=qj)
        assert rj
        assert set(rj.keys()) == {'pysb', 'pybel', 'signed_graph',
                                  'unsigned_graph'}, set(rj.keys())

    def test_temporal_dynamic(self):
        qj = {
            "model": "rasmodel",
            "entity": {
                "type": "Agent",
                "name": "AKT1",
                "db_refs": {"HGNC": "391"}
            },
            "pattern_type": "eventual_value",
            "quant_value": "high"
            }
        rj = self.call_api('post', 'query/temporal_dynamic', json=qj)
        assert rj
        assert set(rj.keys()) == {'pysb'}
        assert 'sat_rate' in rj['pysb']
        assert 'fig_path' in rj['pysb']

    def test_source_target_dynamic(self):
        qj = {
            "model": "rasmodel",
            "source": {
                "type": "Agent",
                "name": "EGFR",
                "db_refs": {"HGNC": "3236"}
            },
            "target": {
                "type": "Agent",
                "name": "AKT1",
                "db_refs": {"HGNC": "391"}
            },
            "direction": "up"
            }
        rj = self.call_api('post', 'query/source_target_dynamic', json=qj)
        assert rj
        assert set(rj.keys()) == {'pysb'}
        assert set(rj['pysb'].keys()) == {'result', 'fig_path'}
