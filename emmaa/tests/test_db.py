from emmaa.db import get_db, Query


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
