import time
import random

from nose.plugins.attrib import attr

from emmaa.db import Query, Result, EmmaaDatabaseManager
from emmaa.queries import Query as QueryObject, PathProperty


test_query_jsons = [{'type': 'path_property', 'path': {'type': 'Activation',
                     'subj': {'type': 'Agent', 'name': 'BRAF'},
                     'obj': {'type': 'Agent', 'name': 'ERK'}}},
                    {'type': 'path_property', 'path':
                    {'type': 'Phosphorylation',
                     'enz': {'type': 'Agent', 'name': 'ERK'},
                     'sub': {'type': 'Agent', 'name': 'MEK'}}}]

test_queries = [QueryObject._from_json(qj) for qj in test_query_jsons]


def _get_test_db():
    db = EmmaaDatabaseManager('postgresql://postgres:@localhost/emmaadb_test')
    db.drop_tables(force=True)
    db.create_tables()
    return db


@attr('nonpublic')
def test_instantiation():
    db = _get_test_db()
    assert db
    return


@attr('nonpublic')
def test_put_queries():
    db = _get_test_db()
    db.put_queries('joshua', 1, test_queries[0], ['aml', 'luad'])
    with db.get_session() as sess:
        queries = sess.query(Query).all()
    assert len(queries) == 2, len(queries)


@attr('nonpublic')
def test_get_queries():
    db = _get_test_db()
    for query in test_queries:
        db.put_queries('joshua', 1, query, ['aml', 'luad'])
        db.put_queries('test_user', 2, query, ['aml'])
    # We should only get distinct queries, independent of number of users
    queries = db.get_queries('aml')
    assert len(queries) == 2, len(queries)
    assert all(isinstance(query, PathProperty) for query in queries)
    queries = db.get_queries('luad')
    assert len(queries) == 2, len(queries)
    assert all(isinstance(query, PathProperty) for query in queries)


def _get_random_result():
    return random.choice(
        [{'12': [['This is fine.', '']]}, {'34': [['This is not ok.', '']]}])


@attr('nonpublic')
def test_put_results():
    db = _get_test_db()
    db.put_queries('joshua', 1, test_queries[0], ['aml', 'luad'])
    queries = db.get_queries('aml')
    results = [(query, '', _get_random_result())
               for query in queries]
    db.put_results('aml', results)
    with db.get_session() as sess:
        db_results = sess.query(Result).all()
    assert len(db_results) == len(results)


@attr('nonpublic')
def test_get_results():
    db = _get_test_db()
    models = ['aml', 'luad']

    # Fill up the database.
    for query in test_queries:
        db.put_queries('joshua', 1, query, models)
    for model in models:
        db.put_results(model, [(query, 'pysb', _get_random_result())
                               for query in test_queries])

    # Try to get the results.
    results = db.get_results('joshua')
    assert len(results) == len(test_queries)*len(models), len(results)
    assert all(isinstance(result, tuple) for result in results)
    assert all(result[0] in models for result in results)
    assert any(results[0][1].matches(q) for q in test_queries)
    assert all(isinstance(result[2], str) for result in results)
    assert all(isinstance(result[3], dict) for result in results)


@attr('nonpublic')
def test_get_latest_results():
    db = _get_test_db()
    models = ['aml', 'luad']

    # Fill up the database.
    for query in test_queries:
        db.put_queries('joshua', 1, query, models)
    for model in models:
        db.put_results(model, [(query, 'pysb', _get_random_result())
                               for query in test_queries])

    # Add the same statements over again
    time.sleep(10)
    for model in models:
        db.put_results(model, [(query, 'pysb', _get_random_result())
                               for query in test_queries])

    # Try to get the results. Make sure we only get the one set.
    results = db.get_results('joshua')
    assert len(results) == len(test_queries)*len(models), len(results)
    assert all(isinstance(result, tuple) for result in results)
    assert all(result[0] in models for result in results)
    assert any(results[0][1].matches(q) for q in test_queries)
    assert all(isinstance(result[2], str) for result in results)
    assert all(isinstance(result[3], dict) for result in results)
