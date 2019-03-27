__all__ = ['EmmaaDatabaseManager', 'EmmaaDatabaseError']

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .schema import EmmaaTable, User, Query

logger = logging.getLogger(__name__)


class EmmaaDatabaseError(Exception):
    pass


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
        logger.debug(f"Grabbing a session to {self.host}...")
        DBSession = sessionmaker(bind=self.engine)
        logger.debug("Session grabbed.")
        session = DBSession()
        if session is None:
            raise EmmaaDatabaseError("Could not acquire session.")
        return session

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

    def add_user(self, email):
        try:
            new_user = User(email)
            self.session.add(new_user)
        except Exception:
            self.session.rollback()
            logger.warning(f"A user with email {email} already exists.")
        self.session.commit()
        return new_user.id

    def put_queries(self, query_json, model_ids):
        # TODO: Handle case where queries already exist
        queries = []
        for model_id in model_ids:
            queries.append({'model_id': model_id, 'json': query_json.copy()})

        with self.get_session() as sess:
            sess.add_all(queries)
        return

    def get_queries(self, model_id):
        with self.get_session() as sess:
            q = sess.query(Query.json).filter(Query.model_id == model_id)
            result = q.all()
        return result

    def put_results(self, model_id, results):
        pass

    def get_results(self, user_id):
        pass
