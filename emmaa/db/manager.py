from fnvhash import fnv1a_32

__all__ = ['EmmaaDatabaseManager', 'EmmaaDatabaseError']

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .schema import EmmaaTable, User, Query, Base, Result

logger = logging.getLogger(__name__)


class EmmaaDatabaseError(Exception):
    pass


class EmmaaDatabaseSessionManager(object):
    def __init__(self, host, engine):
        logger.debug(f"Grabbing a session to {host}...")
        DBSession = sessionmaker(bind=engine)
        logger.debug("Session grabbed.")
        self.session = DBSession()
        if self.session is None:
            raise EmmaaDatabaseError("Could not acquire session.")
        return

    def __enter__(self):
        return self.session

    def __exit__(self, exception_type, exception_value, traceback):
        if exception_type:
            logger.exception(exception_value)
            logger.info("Got exception: rolling back.")
            self.session.rollback()
        else:
            logger.debug("Committing changes...")
            self.session.commit()

        # Close the session.
        self.session.close()


class EmmaaDatabaseManager(object):
    table_order = ['user', 'query', 'user_query', 'result']

    def __init__(self, host, label=None):
        self.host = host
        self.label = label
        self.engine = create_engine(host)
        self.tables = {tbl.__tablename__: tbl
                       for tbl in EmmaaTable.__subclasses__()}
        self.session = None
        return

    def get_session(self):
        return EmmaaDatabaseSessionManager(self.host, self.engine)

    def create_tables(self, tables=None):
        if tables is None:
            tables = set(self.tables.keys())
        else:
            tables = set(tables)

        for tbl_name in self.table_order:
            if tbl_name in tables:
                logger.info(f"Creating {tbl_name} table")
                if not self.tables[tbl_name].__table__.exists(self.engine):
                    self.tables[tbl_name].__table__.create(bind=self.engine)
                    logger.debug("Table created!")
                else:
                    logger.warning(f"Table {tbl_name} already exists! "
                                   f"No action taken.")
        return

    def drop_tables(self, tables=None, force=False):
        """Drop the tables from the EMMAA database given in `tables`.

        If `tables` is None, all tables will be dropped. Note that if `force`
        is False, a warning prompt will be raised to asking for confirmation,
        as this action will remove all data from that table.
        """
        if not force:
            # Build the message
            if tables is None:
                msg = ("Do you really want to clear the %s database? [y/N]: "
                       % self.label)
            else:
                msg = "You are going to clear the following tables:\n"
                msg += str([tbl.__tablename__ for tbl in tables]) + '\n'
                msg += ("Do you really want to clear these tables from %s? "
                        "[y/N]: " % self.label)

            # Check to make sure.
            resp = input(msg)
            if resp != 'y' and resp != 'yes':
                logger.info('Aborting drop.')
                return False

        if tables is None:
            logger.info("Removing all tables...")
            Base.metadata.drop_all(self.engine)
            logger.debug("All tables removed.")
        else:
            for tbl in tables:
                logger.info("Removing %s..." % tbl.__tablename__)
                if tbl.__table__.exists(self.engine):
                    tbl.__table__.drop(self.engine)
                    logger.debug("Table removed.")
                else:
                    logger.debug("Table doesn't exist.")
        return True

    def add_user(self, email):
        try:
            new_user = User(email)
            with self.get_session() as sess:
                sess.add(new_user)
        except Exception:
            logger.warning(f"A user with email {email} already exists.")
        return new_user.id

    def put_queries(self, query_json, model_ids):
        if not isinstance(model_ids, list):
            raise TypeError("Invalid type: %s" % type(model_ids))
        # TODO: Handle case where queries already exist
        # TODO: Unclude user info
        queries = []
        for model_id in model_ids:
            qh = hash_query(query_json, model_id)
            queries.append(Query(model_id=model_id, json=query_json.copy(),
                                 hash=qh))

        with self.get_session() as sess:
            sess.add_all(queries)
        return

    def get_queries(self, model_id):
        with self.get_session() as sess:
            q = sess.query(Query.json).filter(Query.model_id == model_id)
            queries = [q for q, in q.all()]
        return queries

    def put_results(self, model_id, query_results):
        results = []
        for query_json, result_string in query_results:
            query_hash = hash_query(query_json, model_id)
            results.append(Result(query_hash=query_hash, string=result_string))

        with self.get_session() as sess:
            sess.add_all(results)
        return

    def get_results(self, user_id):
        with self.get_session() as sess:
            q = (sess.query(Query.model_id, Query.json,
                            Result.string, Result.date)
                 .filter(Query.hash == Result.query_hash))
            ret = [tuple(res) for res in q.all()]
        return ret


def sorted_json_string(json_thing):
    if isinstance(json_thing, str):
        return json_thing
    elif isinstance(json_thing, list):
        return '[%s]' % (','.join(sorted(sorted_json_string(s)
                                         for s in json_thing)))
    elif isinstance(json_thing, dict):
        return '{%s}' % (','.join(sorted(k + sorted_json_string(v)
                                         for k, v in json_thing.items())))
    else:
        raise TypeError(f"Invalid type: {type(json_thing)}")


def hash_query(query_json, model_id):
    unique_string = model_id + ':' + sorted_json_string(query_json)
    return fnv1a_32(unique_string.encode('utf-8'))
