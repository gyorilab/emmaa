import logging
import pickle
from datetime import datetime
from emmaa.util import get_s3_client, make_date_str
from emmaa.db import get_db


logger = logging.getLogger(__name__)


model_manager_cache = {}


class QueryManager(object):
    """Manager to run queries and interact with the database.

    Parameters
    ----------
    db_name : str
        Name of the database to use
    model_managers : list[emmaa.model_tests.ModelManager]
        Optional list of ModelManagers to use for running queries. If not
        given, the methods will load ModelManager from S3 when needed.
    """
    def __init__(self, db=None, model_managers=None):
        self.db = db
        if db is None:
            self.db = get_db('primary')
        self.model_managers = model_managers if model_managers else []

    def answer_immediate_query(
            self, user_email, query, model_names, subscribe):
        """This method first tries to find saved result to the query in the
        database and if not found, runs ModelManager method to answer query."""
        # Store query in the database for future reference.
        self.db.put_queries(user_email, query, model_names, subscribe)
        # Check if the query has already been answered for any of given models
        # and retrieve the results from database.
        saved_results = self.db.get_results_from_query(query, model_names)
        if not saved_results:
            saved_results = []
        checked_models = {res[0] for res in saved_results}
        # If the query was answered for all models before, return the results.
        if checked_models == set(model_names):
            return format_results(saved_results)
        # Run queries mechanism for models for which result was not found.
        new_results = []
        new_date = datetime.now()
        for model_name in model_names:
            if model_name not in checked_models:
                mm = self.get_model_manager(model_name)
                response = mm.answer_query(query)
                new_results.append((model_name, query, response, new_date))
                if subscribe:
                    self.db.put_results(model_name, [(query, response)])
        all_results = saved_results + new_results
        return format_results(all_results)

    def answer_registered_queries(
            self, model_name, find_delta=True, notify=False):
        """Retrieve queries registered on database for a given model,
        answer them, calculate delta between results, notify users in case of
        any changes, and put results to a database.
        """
        model_manager = self.get_model_manager(model_name)
        queries = self.db.get_queries(model_name)
        # Only do the following steps if there are queries for this model
        if queries:
            results = model_manager.answer_queries(queries)
            # Optionally find delta between results
            # NOTE: For now the report is presented in the logs. In future we can
            # choose some other ways to keep track of result changes.
            if find_delta:
                for query, result_json in results:
                    try:
                        old_results = self.db.get_results_from_query(
                                        query, [model_name], latest_order=1)
                        old_result_json = old_results[0][2]
                    except IndexError:
                        logger.info('No previous result was found.')
                        old_result_json = None
                    logger.info(self.make_str_report_one_query(
                        model_name, query, result_json, old_result_json))
                    # Optionally notify users if there's a change in result
                    if notify:
                        if is_query_result_diff(result_json, old_result_json):
                            users = self.db.get_users(query)
                            for user in users:
                                self.notify_user(
                                    user, model_name, query,
                                    result_json, old_result_json)
            self.db.put_results(model_name, results)

    def get_registered_queries(self, user_email):
        """Get formatted results to queries registered by user."""
        results = self.db.get_results(user_email)
        return format_results(results)

    def get_user_query_delta(
            self, user_email, filename='query_delta', report_format='str'):
        """Produce a report for all query results per user in a given format."""
        results = self.db.get_results(user_email, latest_order=1)
        if report_format == 'str':
            filename = filename + '.txt'
            self.make_str_report_per_user(results, filename=filename)
        elif report_format == 'html':
            filename = filename + '.html'
            self.make_html_report_per_user(results, filename=filename)

    def get_report_per_query(self, model_name, query):
        try:
            new_results = self.db.get_results_from_query(
                            query, [model_name], latest_order=1)
            new_result_json = new_results[0][2]
        except IndexError:
            logger.info('No latest result was found.')
            new_result_json = None
        try:
            old_results = self.db.get_results_from_query(
                            query, [model_name], latest_order=2)
            old_result_json = old_results[0][2]
        except IndexError:
            logger.info('No previous result was found.')
            old_result_json = None
        return self.make_str_report_one_query(
            model_name, query, new_result_json, old_result_json)

    def make_str_report_per_user(self, results, filename='query_delta.txt'):
        """Produce a report for all query results per user in a text file."""
        with open(filename, 'w') as f:
            for result in results:
                model_name = result[0]
                query = result[1]
                new_result_json = result[2]
                try:
                    old_results = self.db.get_results_from_query(
                                    query, [model_name], latest_order=2)
                    old_result_json = old_results[0][2]
                except IndexError:
                    logger.info('No previous result was found.')
                    old_result_json = None
                f.write(self.make_str_report_one_query(model_name, query,
                        new_result_json, old_result_json))
    
    def make_html_report_per_user(self, results, filename='query_delta.html'):
        """Produce a report for all query results per user in an html file."""
        msg = '<html><body>'
        for result in results:
            model_name = result[0]
            query = result[1]
            new_result_json = result[2]
            try:
                old_results = self.db.get_results_from_query(
                                query, [model_name], latest_order=2)
                old_result_json = old_results[0][2]
            except IndexError:
                logger.info('No previous result was found.')
                old_result_json = None
            msg += self._make_html_one_query_inner(
                        model_name, query, new_result_json,
                        old_result_json)
        msg += '</body></html>'
        with open(filename, 'w') as f:
            f.write(msg)

    def make_str_report_one_query(
            self, model_name, query, new_result_json, old_result_json=None):
        """Return a string message containing information about a query and any
        change in the results."""
        if is_query_result_diff(new_result_json, old_result_json):
            if not old_result_json:
                msg = f'This is the first result to query {query}. ' \
                      f'\nThe result is:'
                msg += _process_result_to_str(new_result_json)
            else:
                msg = f'A new result to query {query} in {model_name} was ' \
                      f'found.'
                msg += '\nPrevious result was:'
                msg += _process_result_to_str(old_result_json)
                msg += '\nNew result is:'
                msg += _process_result_to_str(new_result_json)
        else:
            msg = f'A result to query {query} did not change. The result is:'
            msg += _process_result_to_str(new_result_json)
        return msg

    def make_html_one_query_report(
            self, model_name, query, new_result_json, old_result_json=None):
        """Return an html page containing information about a query and any
        change in the results."""
        msg = '<html><body>'
        msg += self._make_html_one_query_inner(
                    model_name, query, new_result_json, old_result_json)
        msg += '</body></html>'
        return msg

    def _make_html_one_query_inner(
            self, model_name, query, new_result_json, old_result_json=None):
        # Create an html part for one query to be used in producing html report
            if is_query_result_diff(new_result_json, old_result_json):
                if not old_result_json:
                    msg = f'<p>This is the first result to query {query} in ' \
                          f'{model_name}. The result is:<br>'
                    msg += _process_result_to_html(new_result_json)
                    msg += '</p>'
                else:
                    msg = f'<p>A new result to query {query} in ' \
                          f'{model_name} was found.<br>'
                    msg += '<br>Previous result was:<br>'
                    msg += _process_result_to_html(old_result_json)
                    msg += '<br>New result is:<br>'
                    msg += _process_result_to_html(new_result_json)
                    msg += '</p>'
            else:
                msg = f'<p>A result to query {query} in ' \
                      f'{model_name} did not change. The result is:<br>'
                msg += _process_result_to_html(new_result_json)
                msg += '</p>'
            return msg

    def notify_user(
            self, user_email, model_name, query, new_result_json,
            old_result_json=None):
        """Create a query result delta report and send it to user."""
        str_msg = self.make_str_report_one_query(
            model_name, query, new_result_json, old_result_json)
        html_msg = self.make_html_one_query_report(
            model_name, query, new_result_json, old_result_json)
        # TODO send an email to user
        pass

    def get_model_manager(self, model_name):
        # Try get model manager from class attributes or load from s3.
        for mm in self.model_managers:
            if mm.model.name == model_name:
                return mm
        return load_model_manager_from_s3(model_name)

    def _recreate_db(self):
        self.db.drop_tables(force=True)
        self.db.create_tables()


def is_query_result_diff(new_result_json, old_result_json=None):
    """Return True if there is a delta between results."""
    # NOTE: this function is query-type specific so it may need to be
    # refactored as a method of the Query class:w

    # Return True if this is the first result
    if not old_result_json:
        return True
    # Compare hashes of query results
    old_result_hashes = [k for k in old_result_json.keys()]
    new_result_hashes = [k for k in new_result_json.keys()]
    return not set(new_result_hashes) == set(old_result_hashes)


def format_results(results):
    """Format db output to a standard json structure."""
    formatted_results = []
    for result in results:
        formatted_result = {}
        formatted_result['model'] = result[0]
        query = result[1]
        formatted_result['query'] = _make_query_simple_dict(query)
        response_json = result[2]
        response = _process_result_to_html(response_json)
        formatted_result['response'] = response
        formatted_result['date'] = make_date_str(result[3])
        formatted_results.append(formatted_result)
    return formatted_results


def load_model_manager_from_s3(model_name):
    model_manager = model_manager_cache.get(model_name)
    if model_manager:
        logger.info(f'Loaded model manager for {model_name} from cache.')
        return model_manager
    client = get_s3_client()
    key = f'results/{model_name}/latest_model_manager.pkl'
    logger.info(f'Loading latest model manager for {model_name} model from '
                f'S3.')
    obj = client.get_object(Bucket='emmaa', Key=key)
    body = obj['Body'].read()
    model_manager = pickle.loads(body)
    model_manager_cache[model_name] = model_manager
    return model_manager


def _process_result_to_str(result_json):
    # Remove the links when making text report
    msg = '\n'
    for v in result_json.values():
        for sentence, link in v:
            msg += sentence
    return msg


def _process_result_to_html(result_json):
    # Make clickable links when making htmk report
    response_list = []
    for v in result_json.values():
        for ix, (sentence, link) in enumerate(v):
            if ix > 0:
                response_list.append('<br>')
            response_list.append(
                f'<a href="{link}" target="_blank" '
                f'class="status-link">{sentence}</a>')
        response = ''.join(response_list)
    return response


def _make_query_simple_dict(query):
    """Turn Query object into a simple dictionary for easier representation on
    the dashboard."""
    query_dict = {}
    stmt = query.path_stmt
    query_dict['typeSelection'] = type(stmt).__name__
    subj, obj = stmt.agent_list()
    query_dict['subjectSelection'] = subj.name
    query_dict['objectSelection'] = obj.name
    return query_dict
