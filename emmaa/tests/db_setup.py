from sqlalchemy_utils import create_database, drop_database, database_exists
from emmaa.db import QueryDatabaseManager, StatementDatabaseManager


query_db_url = 'postgresql://postgres:@localhost/emmaadb_test'
stmt_db_url = 'postgresql://postgres:@localhost/emmaadb_stmt_test'


def _get_test_db(db_name='query'):
    if db_name == 'query':
        db = QueryDatabaseManager(query_db_url)
    elif db_name == 'stmt':
        db = StatementDatabaseManager(stmt_db_url)
    return db


def setup_function(db_name, db_url):
    print('setup')
    if database_exists(db_url):
        drop_database(db_url)
    create_database(db_url)
    db = _get_test_db(db_name)
    db.create_tables()


def teardown_function(db_url):
    print('tear')
    drop_database(db_url)


def setup_query_db():
    setup_function('query', query_db_url)


def teardown_query_db():
    teardown_function(query_db_url)


def setup_stmt_db():
    setup_function('stmt', stmt_db_url)


def teardown_stmt_db():
    teardown_function(stmt_db_url)
