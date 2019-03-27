import random

from emmaa.db import get_db, Query, Result


def _test_db():
    db = get_db('AWS test')
    db.drop_tables(force=True)
    db.create_tables()
    return db


def test_instantiation():
    db = _test_db()
    assert db
    return


def test_put_queries():
    db = _test_db()
    test_query = {'objectSelection': 'ERK',
                  'subjectSelection': 'BRAF',
                  'typeSelection': 'activation'}
    db.put_queries(test_query, ['aml', 'luad'])
    with db.get_session() as sess:
        queries = sess.query(Query).all()
    assert len(queries) == 2, len(queries)


def test_get_queries():
    db = _test_db()
    test_queries = [{'objectSelection': 'ERK',
                     'subjectSelection': 'BRAF',
                     'typeSelection': 'activation'},
                    {'objectSelection': 'MEK',
                     'subjectSelection': 'ERK',
                     'typeSelection': 'phosphorylation'}]
    for query in test_queries:
        db.put_queries(query, ['aml', 'luad'])
    queries = db.get_queries('aml')
    assert len(queries) == 2, len(queries)
    assert all(isinstance(query, dict) for query in queries)


def _get_random_result():
    return random.choice(['This is fine.', 'This is not ok.'])


def test_put_results():
    db = _test_db()
    test_query = {'objectSelection': 'ERK',
                  'subjectSelection': 'BRAF',
                  'typeSelection': 'activation'}
    db.put_queries(test_query, ['aml', 'luad'])
    queries = db.get_queries('aml')
    results = [(query, _get_random_result())
               for query in queries]
    db.put_results('aml', results)
    with db.get_session() as sess:
        db_results = sess.query(Result).all()
    assert len(db_results) == len(results)


def test_get_results():
    db = _test_db()
    models = ['aml', 'luad']
    test_queries = [{'objectSelection': 'ERK',
                     'subjectSelection': 'BRAF',
                     'typeSelection': 'activation'},
                    {'objectSelection': 'MEK',
                     'subjectSelection': 'ERK',
                     'typeSelection': 'phosphorylation'}]

    # Fill up the database.
    for query in test_queries:
        db.put_queries(query, models)
    for model in models:
        db.put_results(model, [(query, _get_random_result())
                               for query in test_queries])

    # Try to get the results.
    results = db.get_results('joshua')
    assert len(results) == len(test_queries)*len(models), len(results)
    assert all(isinstance(result, tuple) for result in results)
    assert all(result[0] in models for result in results)
    assert all(result[1] in test_queries for result in results)
    assert all(isinstance(result[2], str) for result in results)
