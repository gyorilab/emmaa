from collections import defaultdict

from fnvhash import fnv1a_32
from sqlalchemy.exc import IntegrityError

__all__ = ['EmmaaDatabaseManager', 'EmmaaDatabaseError']

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .schema import EmmaaTable, User, Query, Base, Result, UserQuery
from emmaa.queries import Query as QueryObject

logger = logging.getLogger(__name__)


class EmmaaDatabaseError(Exception):
    pass


class EmmaaDatabaseSessionManager(object):
    """A Database session context manager that is used by EmmaaDatabaseManager.
    """
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
    """A class used to manage sessions with EMMAA's database."""
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
        """Create the tables from the EMMAA database

        Optionally specify `tables` to be created. List may contain either
        table objects or the string names of the tables.
        """
        # Regularize the type of input to name strings.
        if tables is not None:
            tables = [tbl.__tablename__ if isinstance(tbl, EmmaaTable) else tbl
                      for tbl in tables]

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
        # Regularize the type of input to table objects.
        if tables is not None:
            tables = [tbl if isinstance(tbl, EmmaaTable) else self.tables[tbl]
                      for tbl in tables]

        if not force:
            # Build the message
            if tables is None:
                msg = ("Do you really want to clear the %s database? [y/N]: "
                       % self.label)
            else:
                msg = "You are going to clear the following tables:\n"
                msg += '\n'.join(['\t-' + tbl.__tablename__ for tbl in tables])
                msg += '\n'
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
        """Add a new user's email to Emmaa's User table."""
        try:
            new_user = User(email=email)
            with self.get_session() as sess:
                sess.add(new_user)
                user_id = new_user.id
        except IntegrityError as e:
            logger.warning(f"A user with email {email} already exists.")
        return user_id

    def put_queries(self, user_email, query, model_ids, subscribe=True):
        """Add queries to the database for a given user.

        Note: users are not considered, and user_id is ignored. In future, the
        user will be recorded and used to restrict the scope of get_results.

        Parameters
        ----------
        user_email : str
            (currently unused) the email of the user that entered the queries.
        query : emmaa.queries.Query
            A query object containing all necessary information.
        model_ids : list[str]
            A list of the short, standard model IDs to which the user wishes
            to apply these queries.
        subscribe : bool
            True if the user wishes to subscribe to this query.
        """
        logger.info(f"Got request to put query {query} for {user_email} "
                    f"for {model_ids} with subscribe={subscribe}")

        # Make sure model_ids is a list.
        if not isinstance(model_ids, list) and not isinstance(model_ids, set):
            raise TypeError("Invalid type: %s. Must be list or set."
                            % type(model_ids))

        if not subscribe:
            logger.info("Not subscribing...")
            return

        # Get the existing hashes.
        with self.get_session() as sess:
            existing_hashes = {h for h, in sess.query(Query.hash).all()}

        # TODO: Include user info
        queries = []
        for model_id in model_ids:
            qh = query.get_hash_with_model(model_id)
            if qh not in existing_hashes:
                logger.info(f"Adding query on {model_id} to the db.")
                queries.append(Query(model_id=model_id, json=query.to_json(),
                                     hash=qh))
            else:
                logger.info(f"Skipping {model_id}; already in db.")

        with self.get_session() as sess:
            sess.add_all(queries)
        return

    def get_queries(self, model_id):
        """Get queries that refer to the given model_id.

        Parameters
        ----------
        model_id : str
            The short, standard model ID.

        Returns
        -------
        queries : list[emmaa.queries.Query]
            A list of queries retrieved from the database.
        """
        # TODO: check whether a query is registered or not.
        with self.get_session() as sess:
            q = sess.query(Query.json).filter(Query.model_id == model_id)
            queries = [QueryObject._from_json(q) for q, in q.all()]
        return queries

    def put_results(self, model_id, query_results):
        """Add new results for a set of queries tested on a model_id.

        Parameters
        ----------
        model_id : str
            The short, standard model ID.
        query_results : list of tuples
            A list of tuples of the form (query, result_json), where
            the query is the query object run against the model,
            and the result_json is the json containing corresponding result.
        """
        results = []
        for query, result_json in query_results:
            query_hash = query.get_hash_with_model(model_id)
            results.append(Result(query_hash=query_hash,
                                  result_json=result_json))

        with self.get_session() as sess:
            sess.add_all(results)
        return

    def get_results_from_query(self, query, model_ids, latest_order=1):
        logger.info(f"Got request for results of {query} on {model_ids}.")
        hashes = {query.get_hash_with_model(model_id) for model_id in model_ids}
        with self.get_session() as sess:
            q = (sess.query(Query.model_id, Query.json, Result.result_json,
                            Result.date)
                 .filter(Result.query_hash.in_(hashes),
                         Query.hash == Result.query_hash))
            results = _make_queries_in_results(q.all())
            results = _weed_results(results, latest_order=latest_order)
        logger.info(f"Found {len(results)} results.")
        return results

    def get_results(self, user_email, latest_order=1):
        """Get the results for which the user has registered.

        Note: currently users are not handled, and this will simply return
        all results.

        Parameters
        ----------
        user_email : str
            The email of a user.

        Returns
        -------
        results : list[tuple]
            A list of tuples, each of the form: (model_id, query,
            result_json, date) representing the result of a query run on a
            model on a given date.
        """
        logger.info(f"Got request for results for {user_email}")
        with self.get_session() as sess:
            q = (sess.query(Query.model_id, Query.json,
                            Result.result_json, Result.date)
                 .filter(Query.hash == Result.query_hash))
            results = _make_queries_in_results(q.all())
            results = _weed_results(results, latest_order=latest_order)
        logger.info(f"Found {len(results)} results.")
        return results

    def get_users(self, query, model_id):
        logger.info(f"Got request for users for {query} in {model_id}.")
        with self.get_session() as sess:
            q = (sess.query(User.email).filter(
                    User.id == UserQuery.user_id,
                    Query.hash == query.get_hash_with_model(model_id)))
            users = [q for q, in q.all()]
        return users


def _weed_results(result_iter, latest_order=1):
    # Each element of result_iter: (model_id, query(object), result_json, date)
    result_dict = defaultdict(list)
    for res in result_iter:
        result_dict[res[1].get_hash_with_model(res[0])].append(tuple(res))
    sorted_results = [sorted(res_list, key=lambda r: r[-1])
                      for res_list in result_dict.values()]
    results = [result[-latest_order] for result in sorted_results]
    return results


def _make_queries_in_results(result_iter):
    # Each element of result_iter: (model_id, query_json, result_json, date)
    # Replace query_json with Query object
    results = []
    for res in result_iter:
        query = QueryObject._from_json(res[1])
        results.append((res[0], query, res[2], res[3]))
    return results


def sorted_json_string(json_thing):
    """Produce a string that is unique to a json's contents."""
    if isinstance(json_thing, str):
        return json_thing
    elif isinstance(json_thing, list):
        return '[%s]' % (','.join(sorted(sorted_json_string(s)
                                         for s in json_thing)))
    elif isinstance(json_thing, dict):
        return '{%s}' % (','.join(sorted(k + sorted_json_string(v)
                                         for k, v in json_thing.items())))
    elif isinstance(json_thing, float):
        return str(json_thing)
    else:
        raise TypeError(f"Invalid type: {type(json_thing)}")


def hash_query(query_json, model_id):
    """Create an FNV-1a 32-bit hash from the query json and model_id."""
    unique_string = model_id + ':' + sorted_json_string(query_json)
    return fnv1a_32(unique_string.encode('utf-8'))
