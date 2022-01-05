from collections import defaultdict

from fnvhash import fnv1a_32
from sqlalchemy.exc import IntegrityError

__all__ = ['EmmaaDatabaseManager', 'EmmaaDatabaseError',
           'QueryDatabaseManager', 'StatementDatabaseManager']

import logging

from botocore.exceptions import ClientError
from sqlalchemy import create_engine, func, Float, nullslast
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.expression import FunctionElement
from sqlalchemy.ext.compiler import compiles
from .schema import EmmaaTable, User, Query, Base, Result, UserQuery, \
    UserModel, Statement, QueriesDbTable, StatementsDbTable
from emmaa.queries import Query as QueryObject
from emmaa.model import get_models, load_config_from_s3
from emmaa.util import EMMAA_BUCKET_NAME, load_gzip_json_from_s3, \
    sort_s3_files_by_date_str, strip_out_date, load_json_from_s3
from indra.statements import stmts_from_json

logger = logging.getLogger(__name__)


class EmmaaDatabaseError(Exception):
    pass


# This is used to get the length of JSONB arrays (e.g. number of evidence in
# a statement),see
# https://stackoverflow.com/questions/23060259/sqlalchemy-querying-the-length-json-field-having-an-array
class jsonb_array_length(FunctionElement):
    name = 'jsonb_array_length'


@compiles(jsonb_array_length)
def compile(element, compiler, **kwargs):
    return 'jsonb_array_length(%s)' % compiler.process(element.clauses)


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
    """A parent class used to manage sessions with in EMMAA's databases."""
    # Child classes should set these attributes.
    table_order = []
    table_parent_class = EmmaaTable

    def __init__(self, host, label=None):
        self.host = host
        self.label = label
        self.engine = create_engine(host)
        self.tables = {tbl.__tablename__: tbl
                       for tbl in self.table_parent_class.__subclasses__()}
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


class QueryDatabaseManager(EmmaaDatabaseManager):
    """A class used to manage sessions with EMMAA's query database."""
    table_order = ['user', 'query', 'user_query', 'user_model', 'result']
    table_parent_class = QueriesDbTable

    def add_user(self, user_id, email):
        """Add a new user's email and id to Emmaa's User table."""
        try:
            new_user = User(id=user_id, email=email)
            with self.get_session() as sess:
                sess.add(new_user)
        except IntegrityError as e:
            logger.warning(f"A user with email {email} already exists.")
        return user_id

    def put_queries(self, user_email, user_id, query, model_ids,
                    subscribe=True):
        """Add queries to the database for a given user.

        Parameters
        ----------
        user_email : str
            the email of the user that entered the queries.
        user_id : int
            the user id of the user that entered the queries. Corresponds to
            the user id in the User table in indralab_auth_tools
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

        # Check if anonymous user
        if not user_email and not user_id:
            logger.info(f'User {user_email} is not registered in the user '
                        'database. Query will be stored as anonymous query.')
            # Make sure user_id is a None and not any other object
            # evaluating to False (only None register as NULL in table)
            user_email = 'anonymous@emmaa.bio'
            user_id = None

        # Open database session
        with self.get_session() as sess:
            # Get existing hashes, user's id and user's subscriptions
            existing_hashes = {h for h, in sess.query(Query.hash).all()}
            existing_user_queries = {h for h, in sess.query(
                UserQuery.query_hash).filter(UserQuery.user_id == user_id)}

            # Check if logged in user is in the emmaa user table
            if user_email and user_id:
                res = \
                    sess.query(User.id).filter(User.id == user_id).first()
                if res:
                    logger.info(f'User {user_email} is registered in the '
                                f'user table.')
                else:
                    logger.info(f'{user_email} not in user table. Adding...')
                    self.add_user(user_id=user_id, email=user_email)

            new_queries = []
            new_user_queries = []
            for model_id in model_ids:
                qh = query.get_hash_with_model(model_id)

                # Add to queries if not present
                if qh not in existing_hashes:
                    logger.info(f"Adding query on {model_id} to the db.")
                    new_queries.append(Query(model_id=model_id,
                                             json=query.to_json(),
                                             qtype=query.get_type(),
                                             hash=qh))
                else:
                    logger.info(f"Query for {model_id} already in db.")

                # Add query to UserQuery table or update existing one
                if qh not in existing_user_queries:
                    new_user_queries.append(UserQuery(user_id=user_id,
                                                      query_hash=qh,
                                                      subscription=subscribe,
                                                      count=1))
                    logger.info(f'Registering query on {model_id} for user '
                                f'{user_email}')
                # Update existing query
                else:
                    user_query = sess.query(UserQuery).filter(
                        UserQuery.user_id == user_id,
                        UserQuery.query_hash == qh
                    ).first()
                    logger.info(f'Updating existing query for {user_email} '
                                f'on {model_id} ({qh})')
                    # Update subscription
                    # Set subscribe to True, handle un-subscribe elsewhere
                    if subscribe:
                        user_query = update_subscription(user_query, subscribe)

                    # Update query count
                    user_query.count += 1

            # Add new queries and register them for the user
            sess.add_all(new_queries)
            sess.add_all(new_user_queries)
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
        with self.get_session() as sess:
            q = sess.query(Query.json).filter(
                Query.model_id == model_id,
                Query.hash == UserQuery.query_hash,
                UserQuery.subscription).distinct()
            queries = [QueryObject._from_json(q) for q, in q.all()]
        return queries

    def put_results(self, model_id, query_results):
        """Add new results for a set of queries tested on a model_id.

        Parameters
        ----------
        model_id : str
            The short, standard model ID.
        query_results : list of tuples
            A list of tuples of the form (query, mc_type, result_json), where
            the query is the query object run against the model, mc_type is
            the model type for the result, and the result_json is the json
            containing corresponding result.
        """
        results = []
        for query, mc_type, result_json in query_results:
            query_hash = query.get_hash_with_model(model_id)
            all_result_hashes = self.get_all_result_hashes(query_hash, mc_type)
            if all_result_hashes is not None:
                delta = set(result_json.keys()) - all_result_hashes
                new_all_hashes = all_result_hashes.union(delta)
            else:  # this is the first result
                delta = set()
                new_all_hashes = set(result_json.keys())
            if delta:
                logger.info('New results:')
                for key in delta:
                    logger.info(result_json[key])
            results.append(Result(query_hash=query_hash,
                                  mc_type=mc_type,
                                  result_json=result_json,
                                  all_result_hashes=new_all_hashes,
                                  delta=delta))

        with self.get_session() as sess:
            sess.add_all(results)
        return

    def get_results_from_query(self, query, model_ids, latest_order=1):
        logger.info(f"Got request for results of {query} on {model_ids}.")
        hashes = {query.get_hash_with_model(model_id)
                  for model_id in model_ids}
        return self.get_results_from_hashes(hashes, latest_order=latest_order)

    def get_results_from_hashes(self, query_hashes, latest_order=1):
        logger.info(f"Got request for results of queries with hashes "
                    f"{query_hashes}")
        with self.get_session() as sess:
            q = (sess.query(Query.model_id, Query.json, Result.mc_type,
                            Result.result_json, Result.delta, Result.date)
                 .filter(Result.query_hash.in_(query_hashes),
                         Query.hash == Result.query_hash)).distinct()
            results = _make_queries_in_results(q.all())
            results = _weed_results(results, latest_order=latest_order)
        logger.info(f"Found {len(results)} results.")
        return results

    def get_all_result_hashes(self, qhash, mc_type):
        """Get a set of all result hashes for a given query and mc_type."""
        with self.get_session() as sess:
            q = (sess.query(Result.all_result_hashes)
                 .filter(Result.query_hash == qhash,
                         Result.mc_type == mc_type)
                 .order_by(Result.date.desc()).limit(1))
        all_sets = [q for q in q.all()]
        if all_sets:
            return set(all_sets[0][0])
        return None

    def get_results(self, user_email, latest_order=1, query_type=None):
        """Get the results for which the user has registered.

        Parameters
        ----------
        user_email : str
            The email of a user.
        latest_order : int
            Which result in the order from the latest to get. Default: 1 (
            latest).
        query_type : str
            Filter results to specific query type. Default: None (all query
            types will be returned).

        Returns
        -------
        results : list[tuple]
            A list of tuples, each of the form: (model_id, query, mc_type,
            result_json, delta, date) representing the result of a query run
            on a model on a given date.
        """
        logger.info(f"Got request for results for {user_email}")
        with self.get_session() as sess:
            q = (sess.query(Query.model_id, Query.json, Result.mc_type,
                            Result.result_json, Result.delta, Result.date)
                 .filter(Query.hash == Result.query_hash,
                         Query.hash == UserQuery.query_hash,
                         UserQuery.user_id == User.id,
                         UserQuery.subscription,
                         User.email == user_email))
            if query_type:
                q = q.filter(Query.qtype == query_type)
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

    def get_subscribed_queries(self, email):
        """Get a list of (query object, model id, query hash) for a user

        Parameters
        ----------
        email : str
            The email address to check subscribed queries for

        Returns
        -------
        list(tuple(emmaa.queries.Query, str, query_hash))
        """
        logger.info(f"Got request to list user queries for {email}")
        # Get the query json for which email is subscribed
        with self.get_session() as sess:
            q = sess.query(Query.json, Query.model_id, Query.hash).filter(
                Query.hash == UserQuery.query_hash,
                UserQuery.user_id == User.id,
                User.email == email,
                UserQuery.subscription
            )
            # Returns list of (query json, query hash) tuples
        return [(QueryObject._from_json(qj), mid, qh)
                for qj, mid, qh in q.all()] if q.all() else []

    def get_subscribed_users(self):
        """Get all users who have subscriptions
        Returns
        -------
        list[str]
            A list of email addresses corresponding to all users who have
            any subscribed query
        """
        logger.info('Got request to gather all users with subscription')
        # Get db session
        with self.get_session() as sess:
            q = sess.query(User.email).filter(
                User.id == UserQuery.user_id,
                UserQuery.subscription
            ).distinct()
        return [e for e, in q.all()] if q.all() else []

    def get_user_models(self, email):
        """Get all models a user is subscribed to."""
        logger.info(f"Got request to list subscribed models for {email}")
        with self.get_session() as sess:
            q = sess.query(UserModel.model_id).filter(
                UserModel.user_id == User.id,
                User.email == email,
                UserModel.subscription
            ).distinct()
        return [m for m, in q.all()] if q.all() else []

    def update_email_subscription(self, email, queries, models, subscribe):
        """Update email subscriptions for user queries

        NOTE:
        For now this method simply unsubscribes to the given queries but
        should in the future differentiated into recieving email
        notifications or not and subscribing to queries or not.

        Parameters
        ----------
        email : str
            The email assocaited with the query
        queries : list(int)
            A list of query hashes.
        models " list[str]
            A list of models.
        subscribe : bool
            The subscription status for all matching query hashes

        Returns
        -------
        bool
            Return True if the update was successful, False otherwise
        """
        logger.info(f'Got request to update email subscription for {email} '
                    f'on {len(queries)} queries and {len(models)} models')
        try:
            updated_queries = 0
            updated_models = 0
            with self.get_session() as sess:
                # First unsubscribe queries
                for qhash in queries:
                    # Update subscription status for each provided hash
                    user_query = sess.query(UserQuery).filter(
                        User.email == email,
                        UserQuery.user_id == User.id,
                        UserQuery.query_hash == qhash
                    )
                    uq = user_query.all()[0] if len(user_query.all()) > 0 \
                        else None

                    # If entry exists and subscription status is different
                    # from new status
                    if uq and uq.subscription != subscribe:
                        uq = update_subscription(uq, subscribe)
                        updated_queries += 1
                    else:
                        continue
                if updated_queries:
                    logger.info(f'Changed subscription status for '
                                f'{updated_queries} queries to {subscribe}. '
                                f'The other {len(queries) - updated_queries} '
                                f'queries already had their subscription '
                                f'status set to {subscribe}.')
                # Then unsubscribe models
                for model_id in models:
                    user_model = sess.query(UserModel).filter(
                        User.email == email,
                        UserModel.user_id == User.id,
                        UserModel.model_id == model_id
                    )
                    um = user_model.all()[0] if len(user_model.all()) > 0 \
                        else None
                    # If entry exists and subscription status is different
                    # from new status
                    if um and um.subscription != subscribe:
                        um = update_model_subscription(um, subscribe)
                        updated_models += 1
                    else:
                        continue
                if updated_models:
                    logger.info(f'Changed subscription status for '
                                f'{updated_models} models to {subscribe}. '
                                f'The other {len(models) - updated_models} '
                                f'models already had their subscription '
                                f'status set to {subscribe}.')
            return True
        except Exception as e:
            logger.warning(f'Could not change subscription status for query '
                           f'hashes {queries} and models {models}.')
            logger.exception(e)
            return False

    def get_number_of_results(self, query_hash, mc_type):
        with self.get_session() as sess:
            q = (sess.query(Result.id).filter(Result.query_hash == query_hash,
                                              Query.hash == Result.query_hash,
                                              Result.mc_type == mc_type))
        return len(q.all())

    def subscribe_to_model(self, user_email, user_id, model_id):
        """Subsribe a user to model updates.

        Parameters
        ----------
        user_email : str
            the email of the user that entered the queries.
        user_id : int
            the user id of the user that entered the queries. Corresponds to
            the user id in the User table in indralab_auth_tools
        model_id : str
            Standard model ID to which the user wishes to subscribe.
        """
        if not user_email or not user_id or not model_id:
            raise TypeError('User email, user id and model id are required')
        with self.get_session() as sess:
            # Check if user is in the emmaa user table
            res = sess.query(User.id).filter(User.id == user_id).first()
            if res:
                logger.info(f'User {user_email} is registered in the '
                            f'user table.')
            else:
                logger.info(f'{user_email} not in user table. Adding...')
                self.add_user(user_id=user_id, email=user_email)
            all_user_models = {m for m, in sess.query(
                UserModel.model_id).filter(UserModel.user_id == user_id)}
            if model_id in all_user_models:
                user_model = sess.query(UserModel).filter(
                    UserModel.user_id == user_id,
                    UserModel.model_id == model_id).first()
                user_model = update_model_subscription(user_model, True)
            else:
                logger.info(
                    f'Subscribing user {user_email} to {model_id} model')
                user_model = UserModel(user_id=user_id,
                                       model_id=model_id,
                                       subscription=True)
                sess.add(user_model)
        return

    def get_model_users(self, model_id):
        """Get all users who are subscribed to a given model.

        Parameters
        ----------
        model_id : str
            A standard name of a model to get users for.

        Returns
        -------
        list[str]
            A list of email addresses corresponding to all users who are
            subscribed to this model.
        """
        logger.info(f'Got request to gather users subscribed to {model_id}')
        # Get db session
        with self.get_session() as sess:
            q = sess.query(User.email).filter(
                User.id == UserModel.user_id,
                UserModel.model_id == model_id,
                UserModel.subscription
            ).distinct()
        return [e for e, in q.all()] if q.all() else []


class StatementDatabaseManager(EmmaaDatabaseManager):
    """A class used to manage sessions with EMMAA's query database."""
    table_order = ['statement']
    table_parent_class = StatementsDbTable

    def build_from_s3(self, number_of_updates=7, bucket=EMMAA_BUCKET_NAME):
        """
        Build the database from S3 files.
        NOTE: This deletes existing database entries and repopulates the tables.
        """
        self.drop_tables()
        self.create_tables()
        # Add each model one by one
        for model, config in get_models(include_config=True):
            self.add_model_from_s3(model, config, number_of_updates, bucket)

    def add_model_from_s3(self, model_id, config=None, number_of_updates=7,
                          bucket=EMMAA_BUCKET_NAME):
        """Add data for one model from S3 files."""
        if not config:
            config = load_config_from_s3(model_id)
        test_corpora = config['test']['test_corpus']
        if isinstance(test_corpora, str):
            test_corpora = [test_corpora]
        stmt_files = sort_s3_files_by_date_str(
            bucket, f'assembled/{model_id}/statements_', '.gz')
        stmt_files_to_use = stmt_files[:number_of_updates]
        for stmt_file in stmt_files_to_use:
            date = strip_out_date(stmt_file, 'date')
            dt = strip_out_date(stmt_file, 'datetime')
            # First get and add statements
            stmt_jsons = load_gzip_json_from_s3(bucket, stmt_file)
            self.add_statements(model_id, date, stmt_jsons)
            # Also update the path counts from each test corpus
            for test_corpus in test_corpora:
                key = f'results/{model_id}/results_{test_corpus}_{dt}.json'
                try:
                    results = load_json_from_s3(bucket, key)
                    path_counts = results[0].get('path_stmt_counts')
                    if path_counts:
                        self.update_statements_path_counts(
                            model_id, date, path_counts)
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        logger.warning(f'No results file for {key}, skipping')
                        continue
                    else:
                        raise e

    def delete_statements(self, model_id, date):
        """Delete statements from the database."""
        logger.info(f'Got request to delete stmts for {model_id} on {date}')
        with self.get_session() as sess:
            q = sess.query(Statement).filter(
                Statement.model_id == model_id,
                Statement.date == date)
            q.delete(synchronize_session=False)

    def add_statements(self, model_id, date, stmt_jsons, max_updates=7):
        """Add statements to the database.

        Parameters
        ----------
        model_id : str
            The standard name of the model to add statements to.
        date : str
            The date when the model was generated.
        stmt_jsons : list[dict]
            A list of statement JSONs to add to the database.
        max_updates : int
            The maximum number of model states to keep in the database. If it
            is reached, the oldest model state will be deleted.

        Returns
        -------
        bool
            True if the statements were added successfully, False otherwise.
        """
        logger.info(f'Got request to add {len(stmt_jsons)} statements to '
                    f'model {model_id} on date {date}')
        while self.get_number_of_dates(model_id) > max_updates - 1:
            oldest_date = self.get_oldest_date(model_id)
            logger.info(f'Deleting statements from {oldest_date}')
            self.delete_statements(model_id, oldest_date)
        stmts_to_add = [Statement(model_id=model_id, date=date,
                                  stmt_hash=stmt_json['matches_hash'],
                                  statement_json=stmt_json)
                        for stmt_json in stmt_jsons]
        with self.get_session() as sess:
            sess.add_all(stmts_to_add)
        logger.info(f'Added {len(stmt_jsons)} statements to db')
        return

    def get_statements(self, model_id, date, offset=0, limit=None,
                       sort_by=None, stmt_types=None, min_belief=None,
                       max_belief=None):
        """Load the statements by model and date.

        Parameters
        ----------
        model_id : str
            The standard name of the model to get statements for.
        date : str
            The date when the model was generated.
        offset : int
            The offset to start at.
        limit : int
            The number of statements to return.

        Returns
        -------
        list[indra.statements.Statement]
            A list of statements corresponding to the model and date.
        """
        logger.info(f'Got request to get statements for model {model_id} '
                    f'on date {date} with offset {offset} and limit {limit} '
                    f'and sort by {sort_by}')
        with self.get_session() as sess:
            q = sess.query(Statement.statement_json).filter(
                Statement.model_id == model_id,
                Statement.date == date
            )
            if stmt_types:
                stmt_types = [stmt_type.lower() for stmt_type in stmt_types]
                q = q.filter(
                    func.lower(Statement.statement_json[
                        'type'].astext).in_(stmt_types))
            if min_belief:
                q = q.filter(
                    Statement.statement_json['belief'].astext.cast(
                        Float) >= float(min_belief))
            if max_belief:
                q = q.filter(
                    Statement.statement_json['belief'].astext.cast(
                        Float) <= float(max_belief))
            if sort_by == 'evidence':
                q = q.order_by(nullslast(jsonb_array_length(
                    Statement.statement_json["evidence"]).desc()))
            elif sort_by == 'belief':
                q = q.order_by(
                    nullslast(Statement.statement_json['belief'].desc()))
            elif sort_by == 'paths':
                q = q.order_by(Statement.path_count.desc())
            if offset:
                q = q.offset(offset)
            if limit:
                q = q.limit(limit)
            stmts = stmts_from_json([s for s, in q.all()])
            logger.info(f'Got {len(stmts)} statements')
        return stmts

    def get_statements_by_hash(self, model_id, date, stmt_hashes):
        """Get statements by hash.

        Parameters
        ----------
        model_id : str
            The standard name of the model to get statements for.
        date : str
            The date when the model was generated.
        stmt_hashes : list[str]
            A list of statement hashes to get statements for.

        Returns
        -------
        list[indra.statements.Statement]
            A list of statements corresponding to the model and date.
        """
        logger.info(f'Got request to get statements for model {model_id} '
                    f'on date {date} for {len(stmt_hashes)} hashes')
        with self.get_session() as sess:
            q = sess.query(Statement.statement_json).filter(
                Statement.model_id == model_id,
                Statement.date == date,
                Statement.stmt_hash.in_(stmt_hashes)
            )
            stmts = stmts_from_json([s for s, in q.all()])
        return stmts

    def update_statements_path_counts(self, model_id, date, path_counts):
        """Update the path counts for statements. The update is incremental
        because we can have the statement used in the paths in different
        test corpora.

        Parameters
        ----------
        model_id : str
            The standard name of the model.
        date : str
            The date when the model was generated.
        path_counts : dict[int, int]
            A dictionary mapping statement hashes to the number of times they
            were used in the paths.
        """
        logger.info(f'Got request to update path counts for {len(path_counts)}'
                    f' statements for model {model_id} on date {date}')
        with self.get_session() as sess:
            for stmt_hash, path_count in path_counts.items():
                stmt = sess.query(Statement).filter(
                    Statement.model_id == model_id,
                    Statement.date == date,
                    Statement.stmt_hash == stmt_hash).first()
                if stmt:
                    stmt.path_count += path_count
                else:
                    logger.warning(f'Statement {stmt_hash} not found in db '
                                   f'for model {model_id} on date {date}')

    def get_path_counts(self, model_id, date):
        """Get the path counts for statements.

        Parameters
        ----------
        model_id : str
            The standard name of the model.
        date : str
            The date when the model was generated.

        Returns
        -------
        dict[str, int]
            A dictionary mapping statement hashes to the number of times they
            were used in the paths.
        """
        logger.info(f'Got request to get path counts for model {model_id} '
                    f'on date {date}')
        with self.get_session() as sess:
            q = sess.query(Statement.stmt_hash, Statement.path_count).filter(
                Statement.model_id == model_id,
                Statement.date == date
            )
            path_counts = {
                str(stmt_hash): path_count for stmt_hash, path_count in q.all()
                if path_count > 0
            }
        return path_counts

    def get_number_of_dates(self, model_id):
        """Get the number of unique dates this model is available for.

        Parameters
        ----------
        model_id : str
            The standard name of the model.

        Returns
        -------
        int
            The number of unique dates this model is available for.
        """
        logger.info(f'Got request to get number of dates for model {model_id}')
        with self.get_session() as sess:
            q = sess.query(Statement.date).filter(
                Statement.model_id == model_id).distinct()
            return q.count()

    def get_oldest_date(self, model_id):
        """Get the oldest date this model is available for.

        Parameters
        ----------
        model_id : str
            The standard name of the model.

        Returns
        -------
        str
            The oldest date this model is available for.
        """
        logger.info(f'Got request to get oldest date for model {model_id}')
        with self.get_session() as sess:
            q = sess.query(Statement.date).filter(
                Statement.model_id == model_id).order_by(
                    Statement.date.asc()).first()
            return q.date if q else None


def _weed_results(result_iter, latest_order=1):
    # Each element of result_iter:
    # (model_id, query(object), result_json, delta, date)
    result_dict = defaultdict(list)
    for res in result_iter:
        result_dict[(res[1].get_hash_with_model(res[0]), res[2])].append(
            tuple(res))
    sorted_results = [sorted(res_list, key=lambda r: r[-1])
                      for res_list in result_dict.values()]
    results = [result[-latest_order] for result in sorted_results]
    return results


def _make_queries_in_results(result_iter):
    # Each element of result_iter:
    # (model_id, query_json, result_json, delta, date)
    # Replace query_json with Query object
    results = []
    for res in result_iter:
        query = QueryObject._from_json(res[1])
        results.append((res[0], query, res[2], res[3], res[4], res[5]))
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


def update_subscription(user_query, new_sub_status):
    """Update a UserQuery object's subscription status

    user_query : `emmaa.db.schema.UserQuery`
        The UserQuery object to be updated
    new_sub_status : Bool
        The subscription status to change to

    Returns
    -------
    user_query : UserQuery(object)
        The updated UserQuery object
    """
    if new_sub_status is not user_query.subscription:
        user_query.subscription = new_sub_status
        logger.info(f'Updated subscription status to '
                    f'{new_sub_status} for query {user_query.query_hash}')
    return user_query


def update_model_subscription(user_model, new_sub_status):
    """Update a UserQuery object's subscription status

    user_query : `emmaa.db.schema.UserModel`
        The UserModel object to be updated
    new_sub_status : Bool
        The subscription status to change to

    Returns
    -------
    user_model : UserModel(object)
        The updated UserModel object
    """
    if new_sub_status is not user_model.subscription:
        user_model.subscription = new_sub_status
        logger.info(f'Updated subscription status to '
                    f'{new_sub_status} for model {user_model.model_id}')
    return user_model
