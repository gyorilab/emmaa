from datetime import datetime
from nose.plugins.attrib import attr
from emmaa.answer_queries import QueryManager, format_results, \
    load_model_manager_from_s3, _is_diff
from emmaa.queries import Query
from emmaa.model_tests import ModelManager
from emmaa.db import get_db
from indra.statements.statements import Activation
from indra.statements.agent import Agent


# Tell nose to not run tests in the imported modules
format_results.__test__ = False
load_model_manager_from_s3.__test__ = False
ModelManager.__test__ = False
Activation.__test__ = False
Agent.__test__ = False
get_db.__test__ = False
Query.__test__ = False
QueryManager.__test__ = False
_is_diff.__test__ = False


test_query = {'type': 'path_property', 'path': {
              'type': 'Activation', 'subj': {'type': 'Agent', 'name': 'BRAF'},
              'obj': {'type': 'Agent', 'name': 'MAPK1'}}}
simple_query = {'typeSelection': 'Activation',
                'subjectSelection': 'BRAF',
                'objectSelection': 'MAPK1'}
query_object = Query._from_json(test_query)
test_response = {3801854542: [
    ('BRAF activates MAP2K1.',
     'https://db.indra.bio/statements/from_agents?subject=1097@HGNC&object=6840@HGNC&type=Activation&format=html'),
    ('Active MAP2K1 activates MAPK1.',
     'https://db.indra.bio/statements/from_agents?subject=6840@HGNC&object=6871@HGNC&type=Activation&format=html')]}
processed_link = '<a href="https://db.indra.bio/statements/from_agents?subject=1097@HGNC&object=6840@HGNC&type=Activation&format=html" target="_blank" class="status-link">BRAF activates MAP2K1.</a>'
query_not_appl = {2413475507: [
    ('Query is not applicable for this model',
     'https://emmaa.readthedocs.io/en/latest/dashboard/response_codes.html')]}


def test_load_model_manager_from_s3():
    mm = load_model_manager_from_s3('test')
    assert isinstance(mm, ModelManager)


def test_format_results():
    results = [('test', query_object, test_response, datetime.now())]
    formatted_results = format_results(results)
    assert len(formatted_results) == 1
    assert formatted_results[0]['model'] == 'test'
    assert formatted_results[0]['query'] == simple_query
    assert isinstance(formatted_results[0]['response'], str)
    assert isinstance(formatted_results[0]['date'], str)


@attr('nonpublic')
def test_answer_immediate_query():
    qm = QueryManager(db_name='test')
    qm._recreate_db()
    results = qm.answer_immediate_query('tester@test.com', query_object,
                                        ['test'], subscribe=False)
    assert len(results) == 1
    assert results[0]['model'] == 'test'
    assert results[0]['query'] == simple_query
    assert isinstance(results[0]['response'], str)
    assert 'BRAF activates MAP2K1.' in results[0]['response'], results[0]['response']
    assert isinstance(results[0]['date'], str)


@attr('nonpublic')
def test_answer_get_registered_queries():
    qm = QueryManager(db_name='test')
    qm._recreate_db()
    qm.db.put_queries('tester@test.com', query_object, ['test'], subscribe=True)
    qm.answer_registered_queries('test')
    results = qm.get_registered_queries('tester@test.com')
    assert len(results) == 1
    assert results[0]['model'] == 'test'
    assert results[0]['query'] == simple_query
    assert isinstance(results[0]['response'], str)
    assert 'BRAF activates MAP2K1.' in results[0]['response'], results[0]['response']
    assert isinstance(results[0]['date'], str)


def test_is_diff():
    assert not _is_diff(query_not_appl, query_not_appl)
    assert _is_diff(test_response, query_not_appl)


@attr('nonpublic')
def test_report_one_query():
    qm = QueryManager(db_name='test')
    str_msg = qm.make_str_report_one_query(
        'test', query_object, test_response, query_not_appl)
    assert str_msg
    assert 'A new result to query' in str_msg
    assert 'Query is not applicable for this model' in str_msg
    assert 'BRAF activates MAP2K1.' in str_msg
    html_msg = qm.make_html_one_query_report(
        'test', query_object, test_response, query_not_appl)
    assert html_msg
    assert 'A new result to query' in html_msg
    assert 'Query is not applicable for this model' in html_msg
    assert processed_link in html_msg


@attr('nonpublic')
def test_report_files():
    qm = QueryManager(db_name='test')
    qm._recreate_db()
    qm.db.put_queries('tester@test.com', query_object, ['test'], subscribe=True)
    qm.db.put_results('test', [(query_object, query_not_appl)])
    qm.make_str_report_per_user('tester@test.com', filename='test_query_delta.txt')
    with open('test_query_delta.txt', 'r') as f:
        msg = f.read()
    assert msg
    assert 'This is the first result to query' in msg, msg
    assert 'Query is not applicable for this model' in msg
    qm.db.put_results('test', [(query_object, test_response)])
    qm.make_str_report_per_user('tester@test.com', filename='test_query_delta.txt')
    with open('test_query_delta.txt', 'r') as f:
        msg = f.read()
    assert msg
    assert 'A new result to query' in msg
    assert 'BRAF activates MAP2K1.' in msg
