import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .schema import EmmaaTable


logger = logging.getLogger(__name__)


class EmmaaDatabaseError(Exception):
    pass


class EmmaaDatabaseManager(object):
    table_order = ['user', 'query', 'user_query', 'result']

    def __init__(self, host):
        self.host = host
        self.engine = create_engine(host)
        self.tables = {tbl.__tablename__: tbl
                       for tbl in EmmaaTable.__subclasses__()}
        self.session = None
        return

    def grab_session(self):
        if self.session is None or not self.session.is_active:
            logger.debug(f"Grabbing a session to {self.host}...")
            DBSession = sessionmaker(bind=self.engine)
            logger.debug("Session grabbed.")
            self.session = DBSession()
            if self.session is None:
                raise EmmaaDatabaseError("Could not acquire session.")

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
