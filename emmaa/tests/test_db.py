from emmaa.db import get_db


def _test_db():
    db = get_db('AWS test')
    db.drop_tables(force=True)
    db.create_tables()
    return db


def test_instantiation():
    db = _test_db()
    assert db
    return
