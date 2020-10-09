from sqlalchemy_utils import create_database, drop_database, database_exists
from emmaa.db import EmmaaDatabaseManager


db_url = 'postgresql://postgres:@localhost/emmaadb_test'


def _get_test_db(db_name='emmaadb_test'):
    db = EmmaaDatabaseManager(db_url)
    return db


def setup_function():
    print('setup')
    if database_exists(db_url):
        drop_database(db_url)
    create_database(db_url)
    db = _get_test_db()
    db.create_tables()


def teardown_function():
    print('tear')
    drop_database(db_url)
