import logging
import pickle
from datetime import datetime
from emmaa.util import get_s3_client, make_date_str
from emmaa.db import get_db
from emmaa.queries import Query
from indra.statements.statements import Statement


logger = logging.getLogger(__name__)


model_manager_cache = {}


class QueryManager(object):
    def __init__(self, db_name='primary', model_managers=None):
        self.db = get_db(db_name)
        self.model_managers = model_managers if model_managers else []

    def answer_immediate_query(
            self, user_email, query_dict, model_names, subscribe):
        query = Query._from_json(query_dict)
        query_dict = query.to_json()
        self.db.put_queries(user_email, query_dict, model_names, subscribe)
        # Check if the query has already been answered for any of given models
        # and retrieve the results from database.
        saved_results = self.db.get_results_from_query(query_dict, model_names)
        checked_models = {res[0] for res in saved_results}
        if checked_models == set(model_names):
            return format_results(saved_results)
        # Run queries mechanism for models for which result was not found.
        new_results = []
        new_date = datetime.now()
        for model_name in model_names:
            if model_name not in checked_models:
                mm = self.get_model_manager(model_name)
                response = mm.answer_query(query)
                new_results.append((model_name, query_dict, response, new_date))
                if subscribe:
                    self.db.put_results(model_name, [(query_dict, response)])
        all_results = saved_results + new_results
        return format_results(all_results)

    def get_model_manager(self, model_name):
        # Try get model manager from class attributes or load from s3.
        for mm in self.model_managers:
            if mm.model.name == model_name:
                return mm
        return load_model_manager_from_s3(model_name)

    def answer_registered_queries(self, model_name):
        """Retrieve queries registered on database for a given model,
        answer them, and put results to a database.
        """
        model_manager = self.get_model_manager(model_name)
        query_dicts = self.db.get_queries(model_name)
        queries = [Query._from_json(json) for json in query_dicts]
        results = model_manager.answer_queries(queries)
        self.db.put_results(model_name, results)

    def _recreate_db(self):
        self.db.drop_tables(force=True)
        self.db.create_tables()


def _is_diff(new_result_json, old_result_json):
    """Return True if there is a delta between results."""
    # Compare hashes of query results
    old_result_hashes = [k for k in old_result_json.keys()]
    new_result_hashes = [k for k in new_result_json.keys()]
    return not set(new_result_hashes) == set(previous_result_hashes)


def get_registered_queries(user_email, db_name='primary'):
    """Get formatted results to queries registered by user."""
    db = get_db(db_name)
    results = db.get_results(user_email)
    return format_results(results)


def make_str_report_per_user(user_email, filename='query_delta.txt',
                             db_name='primary'):
    db = get_db(db_name)
    results = db.get_results(user_email, latest_order=1)
    with open(filename, 'w') as f:
        for result in results:
            model_name = result[0]
            query_json = result[1]
            new_result_json = result[2]
            old_result_json = db.get_results_from_query(
                query_json, [model_name], latest_order=2)
            f.write(make_str_report_one_query(model_name, query_json,
                    new_result_json, old_result_json))


def _make_str_report_one_query(model_name, query_json, new_result_json,
                               old_result_json):
    """Return a string message containing information about query and any
    change in the results."""
    if _is_diff(new_result_json, old_result_json):
        msg = f'A new result to query ' \
              f'{Statement._from_json(query_json["path"])} in  {model_name} ' \
              f'was found.'
        msg += '\nPrevious result was:'
        msg += _process_result_to_str(old_result_json)
        msg += '\nNew result is:'
        msg += _process_result_to_str(new_result_json)
    else:
        msg = f'A result to query {Statement._from_json(query_json["path"])}' \
              f' did not change. The result is:'
        msg += _process_result_to_str(new_result_json)
    return msg


def make_html_report_per_user(user_email, filename='query_delta.html',
                              db_name='primary'):
    db = get_db(db_name)
    results = db.get_results(user_email, latest_order=1)
    msg = '<html><body>'
    for result in results:
            model_name = result[0]
            query_json = result[1]
            new_result_json = result[2]
            old_result_json = db.get_results_from_query(
                query_json, [model_name], latest_order=2)
            msg += _make_html_one_query_inner(model_name, query_json,
                                              new_result_json, old_result_json)
    msg += '</body></html>'
    with open(filename, 'w') as f:
        f.write(msg)


def make_html_one_query_report(model_name, query_json, new_result_json,
                               old_result_json):
    msg = '<html><body>'
    msg += _make_html_one_query_inner(model_name, query_json, new_result_json,
                                      old_result_json)
    msg += '</body></html>'
    return msg


def _make_html_one_query_inner(model_name, query_json, new_result_json,
                               old_result_json):
    if _is_diff(new_result_json, old_result_json):
        msg = f'<p>A new result to query ' \
              f'{Statement._from_json(query_json["path"])} in {model_name} ' \
              f'was found.<br>'
        msg += 'Previous result was:<br>'
        msg += _process_result_to_html(old_result_json)
        msg += 'New result is:<br>'
        msg += _process_result_to_html(new_result_json)
        msg += '</p>'
    else:
        msg = f'<p>A result to query ' \
              f'{Statement._from_json(query_json["path"])} in {model_name} ' \
              f'did not change. The result is:<br>'
        msg += _process_result_to_html(new_result_json)
        msg += '</p>'
    return msg


def get_user_query_delta(user_email, db_name='primary',
                         filename='query_delta.txt', report_format='str'):
    if report_format == 'str':
        make_str_report_per_user(user_email, filename=filename, db_name=db_name)
    elif report_format == 'hmtl':
        make_html_report_per_user(user_email, filename=filename, db_name=db_name)


def notify_user(user_email, model_name, query_json, new_result_json,
                old_result_json):
    str_msg = _make_str_report_one_query(model_name, query_json,
                                         new_result_json, old_result_json)
    html_msg = make_html_one_query_report(model_name, query_json,
                                          new_result_json, old_result_json)
    # TODO send an email to user
    pass


def format_results(results):
    """Format db output to a standard json structure."""
    formatted_results = []
    for result in results:
        formatted_result = {}
        formatted_result['model'] = result[0]
        formatted_result['query'] = result[1]
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
    model_manager = pickle.loads(obj['Body'].read())
    model_manager_cache[model_name] = model_manager
    return model_manager


def _process_result_to_str(result_json):
    msg = ''
    for v in old_result_json.values():
            for sentence, link in v:
                msg += sentence
    return msg


def _process_result_to_html(result_json):
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
