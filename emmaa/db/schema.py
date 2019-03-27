__all__ = ['User', 'Query', 'UserQuery', 'Result']

import logging

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, \
    Boolean, DateTime, func, BigInteger
from sqlalchemy.orm import relationship
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
    model_id = Column(String(5))
    json = Column(JSONB, nullable=False)


class UserQuery(Base, EmmaaTable):
    __tablename__ = 'user_query'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = relationship(User)
    query_hash = Column(BigInteger, ForeignKey('query.hash'), nullable=False)
    query = relationship(Query)
    date = Column(DateTime, default=func.now())
    subscription = Column(Boolean, nullable=False)


class Result(Base, EmmaaTable):
    __tablename__ = 'result'
    id = Column(Integer, primary_key=True)
    query_hash = Column(BigInteger, ForeignKey('query.hash'), nullable=False)
    date = Column(DateTime, default=func.now())
    json = Column(JSONB, nullable=False)
