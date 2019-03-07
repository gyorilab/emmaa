from emmaa.db import get_db


def test_instantiation():
    db = get_db('local test')
    db.create_tables()
    return
