from emmaa.answer_queries import (
    answer_immediate_query, answer_registered_queries, get_registered_queries,
    format_results, get_statement_by_query,
    load_model_manager_from_s3)
from emmaa.model_tests import ModelManager
from indra.statements.statements import Activation
from indra.statements.agent import Agent


test_query = {'objectSelection': 'MAPK1', 'subjectSelection': 'BRAF',
              'typeSelection': 'activation'}


def test_get_statement_by_query():
    stmt = get_statement_by_query(test_query)
    assert isinstance(stmt, Activation)
    assert isinstance(stmt.subj, Agent)
    assert isinstance(stmt.obj, Agent)
    assert stmt.subj.name == 'BRAF'
    assert stmt.subj.db_refs == {'HGNC': '1097'}
    assert stmt.obj.name == 'MAPK1'
    assert stmt.obj.db_refs == {'HGNC': '6871'}


def test_load_model_manager_from_s3():
    mm = load_model_manager_from_s3('test')
    assert isinstance(mm, ModelManager)


def test_format_results():
    results = [('test', test_query,
                'BRAF activates MAP2K1. Active MAP2K1 activates MAPK1.',
                '2019-04-01-20-32-20')]
    formatted_results = format_results(results)
    assert len(formatted_results) == 1
    assert formatted_results[0]['model'] == 'test'
    assert formatted_results[0]['query'] == test_query
    assert formatted_results[0]['response'] == (
        'BRAF activates MAP2K1. Active MAP2K1 activates MAPK1.')
    assert formatted_results[0]['date'] == '2019-04-01-20-32-20'


@attr('notravis')
def test_answer_immediate_query():
    db = get_db('test')
    db.drop_tables(force=True)
    db.create_tables()
    results = answer_immediate_query('tester@test.com', test_query, ['test'],
                                     subscribe=False, db_name='test')
    assert len(results) == 1
    assert results[0]['model'] == 'test'
    assert results[0]['query'] == test_query
    assert isinstance(results[0]['response'], str)
    assert isinstance(results[0]['date'], str)


@attr('notravis')
def test_answer_get_registered_queries():
    pass
