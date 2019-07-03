from os.path import abspath, dirname, join
from datetime import datetime
from nose.plugins.attrib import attr
from emmaa.answer_queries import QueryManager, format_results, \
    load_model_manager_from_s3, is_query_result_diff
from emmaa.queries import Query
from emmaa.model_tests import ModelManager
from emmaa.tests.test_db import _get_test_db


test_query = {'type': 'path_property', 'path': {'type': 'Activation',
              'subj': {'type': 'Agent', 'name': 'BRAF',
                       'db_refs': {'HGNC': '1097'}},
              'obj': {'type': 'Agent', 'name': 'MAPK1',
                      'db_refs': {'HGNC': '6871'}}}}
simple_query = {'typeSelection': 'Activation',
                'subjectSelection': 'BRAF',
                'objectSelection': 'MAPK1'}
query_object = Query._from_json(test_query)

test_response = {3801854542: [
    ('BRAF activates MAP2K1.',
     'https://db.indra.bio/statements/from_agents?subject=1097@HGNC&object='
     '6840@HGNC&type=Activation&format=html'),
    ('Active MAP2K1 activates MAPK1.',
     'https://db.indra.bio/statements/from_agents?subject=6840@HGNC&object='
     '6871@HGNC&type=Activation&format=html')]}
processed_link = '<a href="https://db.indra.bio/statements/from_agents?'\
    'subject=1097@HGNC&object=6840@HGNC&type=Activation&format=html" '\
                 'target="_blank" class="status-link">'\
                 'BRAF activates MAP2K1.</a>'
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
    db = _get_test_db()
    qm = QueryManager(db=db)
    qm._recreate_db()
    results = qm.answer_immediate_query('tester@test.com', query_object,
                                        ['test'], subscribe=False)
    assert len(results) == 1
    assert results[0]['model'] == 'test'
    assert results[0]['query'] == simple_query
    assert isinstance(results[0]['response'], str)
    assert 'BRAF activates MAP2K1.' in results[0]['response'], \
        results[0]['response']
    assert isinstance(results[0]['date'], str)


@attr('nonpublic')
def test_answer_get_registered_queries():
    db = _get_test_db()
    qm = QueryManager(db=db)
    qm._recreate_db()
    qm.db.put_queries('tester@test.com', query_object, ['test'],
                      subscribe=True)
    qm.answer_registered_queries('test')
    results = qm.get_registered_queries('tester@test.com')
    assert len(results) == 1
    assert results[0]['model'] == 'test'
    assert results[0]['query'] == simple_query
    assert isinstance(results[0]['response'], str)
    assert 'BRAF activates MAP2K1.' in results[0]['response'], \
        results[0]['response']
    assert isinstance(results[0]['date'], str)


def test_is_diff():
    assert not is_query_result_diff(query_not_appl, query_not_appl)
    assert is_query_result_diff(test_response, query_not_appl)


@attr('nonpublic')
def test_report_one_query():
    db = _get_test_db()
    qm = QueryManager(db=db)
    # Using results from db
    qm.db.put_queries('tester@test.com', query_object, ['test'],
                      subscribe=True)
    qm.db.put_results('test', [(query_object, test_response),
                               (query_object, query_not_appl)])
    str_msg = qm.get_report_per_query('test', query_object)
    assert str_msg
    assert 'A new result to query' in str_msg
    assert 'Query is not applicable for this model' in str_msg
    assert 'BRAF activates MAP2K1.' in str_msg
    # String report given two responses explicitly
    str_msg = qm.make_str_report_one_query(
        'test', query_object, test_response, query_not_appl)
    assert str_msg
    assert 'A new result to query' in str_msg
    assert 'Query is not applicable for this model' in str_msg
    assert 'BRAF activates MAP2K1.' in str_msg
    # Html report given two responses explicitly
    html_msg = qm.make_html_one_query_report(
        'test', query_object, test_response, query_not_appl)
    assert html_msg
    assert 'A new result to query' in html_msg
    assert 'Query is not applicable for this model' in html_msg
    assert processed_link in html_msg


@attr('nonpublic')
def test_report_files():
    db = _get_test_db()
    qm = QueryManager(db=db)
    qm._recreate_db()
    qm.db.put_queries('tester@test.com', query_object, ['test'],
                      subscribe=True)
    qm.db.put_results('test', [(query_object, query_not_appl)])
    results = qm.db.get_results('tester@test.com', latest_order=1)
    qm.make_str_report_per_user(results,
                                filename='test_query_delta.txt')
    report_file = join(dirname(abspath(__file__)), 'test_query_delta.txt')
    with open(report_file, 'r') as f:
        msg = f.read()
    assert msg
    assert 'This is the first result to query' in msg, msg
    assert 'Query is not applicable for this model' in msg
    qm.db.put_results('test', [(query_object, test_response)])
    results = qm.db.get_results('tester@test.com', latest_order=1)
    qm.make_str_report_per_user(results,
                                filename='new_test_query_delta.txt')
    new_report_file = join(dirname(abspath(__file__)),
                           'new_test_query_delta.txt')
    with open(new_report_file, 'r') as f:
        msg = f.read()
    assert msg
    assert 'A new result to query' in msg
    assert 'BRAF activates MAP2K1.' in msg
