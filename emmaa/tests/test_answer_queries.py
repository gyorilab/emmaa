from os.path import abspath, dirname, join
from datetime import datetime
from nose.plugins.attrib import attr
from emmaa.answer_queries import QueryManager, format_results, \
    load_model_manager_from_s3, is_query_result_diff
from emmaa.queries import Query
from emmaa.model_tests import ModelManager
from emmaa.tests.test_db import _get_test_db
from emmaa.model import EmmaaModel


test_query = {'type': 'path_property', 'path': {'type': 'Activation',
              'subj': {'type': 'Agent', 'name': 'BRAF',
                       'db_refs': {'HGNC': '1097'}},
              'obj': {'type': 'Agent', 'name': 'MAPK1',
                      'db_refs': {'HGNC': '6871'}}}}
simple_query = 'Activation(BRAF, MAPK1)'
query_object = Query._from_json(test_query)

test_response = {
    '3801854542': {
        'path': 'BRAF → MAP2K1 → MAPK1',
        'edge_list': [
            {'edge': 'BRAF → MAP2K1',
             'stmts': [
                 ['https://db.indra.bio/statements/from_agents?subject=1097@HGNC&object=6840@HGNC&type=Activation&format=html',
                  'BRAF activates MAP2K1.', '']]},
            {'edge': 'MAP2K1 → MAPK1',
             'stmts': [
                 ['https://db.indra.bio/statements/from_agents?subject=6840@HGNC&object=6871@HGNC&type=Activation&format=html',
                  'Active MAP2K1 activates MAPK1.', '']]}]}}
processed_link = '<a href="https://db.indra.bio/statements/from_agents?'\
    'subject=1097@HGNC&object=6840@HGNC&type=Activation&format=html" '\
                 'target="_blank" class="status-link">'\
                 'BRAF activates MAP2K1.</a>'
query_not_appl = {'2413475507': 'Query is not applicable for this model'}
fail_response = {'521653329': 'No path found that satisfies the test statement'}
# Create a new ModelManager for tests instead of depending on S3 version
test_model = EmmaaModel.load_from_s3('test')
test_mm = ModelManager(test_model)


def test_load_model_manager_from_s3():
    mm = load_model_manager_from_s3('test')
    assert isinstance(mm, ModelManager)


def test_format_results():
    date = datetime.now()
    results = [('test', query_object, 'pysb', test_response, date),
               ('test', query_object, 'signed_graph', fail_response, date),
               ('test', query_object, 'unsigned_graph', test_response, date)]
    formatted_results = format_results(results)
    assert len(formatted_results) == 1
    qh = query_object.get_hash_with_model('test')
    assert qh in formatted_results
    assert formatted_results[qh]['model'] == 'test'
    assert formatted_results[qh]['query'] == simple_query
    assert isinstance(formatted_results[qh]['date'], str)
    assert formatted_results[qh]['pysb'] == [
        'Pass', [test_response['3801854542']]]
    assert formatted_results[qh]['pybel'] == [
        'n_a', 'Model type not supported']
    assert formatted_results[qh]['signed_graph'] == [
        'Fail', fail_response['521653329']]
    assert formatted_results[qh]['unsigned_graph'] == [
        'Pass', [test_response['3801854542']]]


@attr('nonpublic')
def test_answer_immediate_query():
    db = _get_test_db()
    qm = QueryManager(db=db, model_managers=[test_mm])
    query_hashes = qm.answer_immediate_query('tester@test.com', 1, query_object,
                                             ['test'], subscribe=False)
    assert query_hashes == [-4326204908289564]
    results = qm.retrieve_results_from_hashes(query_hashes)
    assert len(results) == 1
    assert query_hashes[0] in results
    result_values = results[query_hashes[0]]
    assert result_values['model'] == 'test'
    assert result_values['query'] == simple_query
    assert isinstance(result_values['date'], str)
    assert result_values['pysb'] == ['Pass', [test_response['3801854542']]]
    assert result_values['pybel'] == ['n_a', 'Model type not supported']
    assert result_values['signed_graph'] == ['n_a', 'Model type not supported']
    assert result_values['unsigned_graph'] == ['n_a', 'Model type not supported']


@attr('nonpublic')
def test_answer_get_registered_queries():
    db = _get_test_db()
    qm = QueryManager(db=db, model_managers=[test_mm])
    qm.db.put_queries('tester@test.com', 1, query_object, ['test'],
                      subscribe=True)
    qm.answer_registered_queries('test')
    results = qm.get_registered_queries('tester@test.com')
    qh = query_object.get_hash_with_model('test')
    assert qh in results
    assert len(results) == 1
    assert results[qh]['model'] == 'test'
    assert results[qh]['query'] == simple_query
    assert isinstance(results[qh]['date'], str)
    assert results[qh]['pysb'] == ['Pass', [test_response['3801854542']]]
    assert results[qh]['pybel'] == ['n_a', 'Model type not supported']
    assert results[qh]['signed_graph'] == ['n_a', 'Model type not supported']
    assert results[qh]['unsigned_graph'] == ['n_a', 'Model type not supported']


def test_is_diff():
    assert not is_query_result_diff(query_not_appl, query_not_appl)
    assert is_query_result_diff(test_response, query_not_appl)


@attr('nonpublic')
def test_report_one_query():
    db = _get_test_db()
    qm = QueryManager(db=db, model_managers=[test_mm])
    # Using results from db
    qm.db.put_queries('tester@test.com', 1, query_object, ['test'],
                      subscribe=True)
    qm.db.put_results('test', [(query_object, 'pysb', test_response),
                               (query_object, 'pysb', query_not_appl)])
    str_msg = qm.get_report_per_query('test', query_object)[0]
    assert str_msg
    assert 'A new result to query' in str_msg
    assert 'Query is not applicable for this model' in str_msg
    assert 'BRAF → MAP2K1 → MAPK1' in str_msg
    # String report given two responses explicitly
    str_msg = qm.make_str_report_one_query(
        'test', query_object, 'pysb', test_response, query_not_appl)
    assert str_msg
    assert 'A new result to query' in str_msg, str_msg
    assert 'Query is not applicable for this model' in str_msg
    assert 'BRAF → MAP2K1 → MAPK1' in str_msg
    # Html report given two responses explicitly
    html_msg = qm.make_html_one_query_report(
        'test', query_object, 'pysb', test_response, query_not_appl)
    assert html_msg
    assert 'A new result to query' in html_msg
    assert 'Query is not applicable for this model' in html_msg


@attr('nonpublic')
def test_report_files():
    db = _get_test_db()
    qm = QueryManager(db=db, model_managers=[test_mm])
    qm.db.put_queries('tester@test.com', 1, query_object, ['test'],
                      subscribe=True)
    qm.db.put_results('test', [(query_object, 'pysb', query_not_appl)])
    results = qm.db.get_results('tester@test.com', latest_order=1)
    qm.make_str_report_per_user(results,
                                filename='test_query_delta.txt')
    report_file = join(dirname(abspath(__file__)), 'test_query_delta.txt')
    with open(report_file, 'r') as f:
        msg = f.read()
    assert msg
    assert 'This is the first result to query' in msg, msg
    assert 'Query is not applicable for this model' in msg
    qm.db.put_results('test', [(query_object, 'pysb', test_response)])
    results = qm.db.get_results('tester@test.com', latest_order=1)
    qm.make_str_report_per_user(results,
                                filename='new_test_query_delta.txt')
    new_report_file = join(dirname(abspath(__file__)),
                           'new_test_query_delta.txt')
    with open(new_report_file, 'r') as f:
        msg = f.read()
    assert msg
    assert 'A new result to query' in msg
    assert 'BRAF → MAP2K1 → MAPK1' in msg
