import logging

from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, \
    create_engine, inspect, LargeBinary, Boolean, DateTime, func, BigInteger
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.dialects.postgresql import JSONB


logger = logging.getLogger(__name__)


Base = declarative_base()


class EmmaaTable(object):
    _skip_disp = []

    def _make_str(self):
        s = self.__tablename__ + ':\n'
        for k, v in self.__dict__.items():
            if not k.startswith('_'):
                if k in self._skip_disp:
                    s += '\t%s: [not shown]\n' % k
                else:
                    s += '\t%s: %s\n' % (k, v)
        return s

    def display(self):
        """Display the values of this entry."""
        print(self._make_str())

    def __str__(self):
        return self._make_str()


class User(Base, EmmaaTable):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)


class Query(Base, EmmaaTable):
    __tablename__ = 'query'
    hash = Column(BigInteger, primary_key=True)
    json = Column(JSONB, nullable=False)


class UserQuery(Base, EmmaaTable):
    __tablename__ = 'user_query'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = relationship(User)
    query_hash = Column(BigInteger, ForeignKey('query.hash'), nullable=False)
    query = relationship(Query)
    date = Column(DateTime, default=func.now())


class Result(Base, EmmaaTable):
    __tablename__ = 'result'
    id = Column(Integer, primary_key=True)
    query_hash = Column(BigInteger, ForeignKey('query.hash'), nullable=False)
    date = Column(DateTime, default=func.now())
    json = Column(JSONB, nullable=False)


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
