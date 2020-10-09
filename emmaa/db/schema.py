__all__ = ['User', 'Query', 'UserQuery', 'Result']

import logging

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, \
    Boolean, DateTime, func, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY


logger = logging.getLogger(__name__)


Base = declarative_base()


class EmmaaTable(object):
    _skip_disp = []

    def _content_strings(self):
        ret = []
        for k, v in self.__dict__.items():
            if not k.startswith('_'):
                if k in self._skip_disp:
                    ret.append(f'{k}=[not shown]')
                else:
                    ret.append(f'{k}={v}')
        return ret

    def _make_str(self):
        s = self.__tablename__ + ':\n'
        s += '\n'.join(f'\t{line}' for line in self._content_strings())
        return s

    def display(self):
        """Display the values of this entry."""
        print(self._make_str())

    def __str__(self):
        return self._make_str()

    def __repr__(self):
        return f'{self.__class__.__name__}' \
               f'({", ".join(self._content_strings())})'


class User(Base, EmmaaTable):
    """A table containing users of EMMAA: ``User(_id_, email)``

    Parameters
    ----------
    id : int
        (from indralab_auth_tools.src.models.User.id, primary key)
        A database-generated integer from the User table in indralab
        auth tools.
    email : str
        The email of the user (must be unique)
    """
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)


class Query(Base, EmmaaTable):
    """Queries run on each model: ``Query(_hash_, model_id, json, qtype)``

    The hash column is a hash generated from the json and model_id columns
    that can be derived from the

    Parameters
    ----------
    hash : big-int
        (primary key) A 32 bit integer generated from the json and model_id.
    model_id : str
        (20 character) The short id/acronym for the given model.
    json : json
        A json dict containing the relevant parameters defining the query.
    """
    __tablename__ = 'query'
    hash = Column(BigInteger, primary_key=True)
    model_id = Column(String(20), nullable=False)
    json = Column(JSONB, nullable=False)
    qtype = Column(String(20), default='path_property')
    __table_args__ = (
        UniqueConstraint('model_id', 'json', name='query-uniqueness'),
        )


class UserQuery(Base, EmmaaTable):
    """A table linking users to queries:

    ``UserQuery(_id_, user_id, query_hash, date, subscription, count)``

    Parameters
    ----------
    id : int
        (auto, primary key) A database-assigned integer id.
    user_id : int
        (foreign key -> User.id) The id of the user related to this query.
    query_hash : big-int
        (foreign key -> Query.hash) The hash of the query json, which can be
        directly generated.
    date : datetime
        (auto) The date that this entry was added to the database.
    subscription : bool
        Record whether the user has subscribed to see results of this model.
    count : int
        Record the number of times the user associated with user id has done
        this query
    """
    __tablename__ = 'user_query'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    user = relationship(User)
    query_hash = Column(BigInteger, ForeignKey('query.hash'), nullable=False)
    query = relationship(Query)
    date = Column(DateTime, default=func.now())
    subscription = Column(Boolean, nullable=False)
    count = Column(Integer, nullable=False)


class Result(Base, EmmaaTable):
    """Results of queries to models:

    ``Result(_id_, query_hash, date, result_json, mc_type, all_result_hashes,
    delta)``

    Parameters
    ----------
    id : int
        (auto, primary key) A database-assigned integer id.
    query_hash : big-int
        (foreign key -> Query.hash) The hash of the query json, which can be
        directly generated.
    date : datetime
        (auto) The date the result was entered into the database.
    result_json : json
        A json dict containing the results for the query.
    mc_type : str
        A name of a ModelChecker used to answer the query.
    """
    __tablename__ = 'result'
    id = Column(Integer, primary_key=True)
    query_hash = Column(BigInteger, ForeignKey('query.hash'), nullable=False)
    query = relationship(Query)
    date = Column(DateTime, default=func.now())
    result_json = Column(JSONB, nullable=False)
    mc_type = Column(String(20), default='pysb')
    all_result_hashes = Column(ARRAY(String), default=[])
    delta = Column(ARRAY(String), default=[])
