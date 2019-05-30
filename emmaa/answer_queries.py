import logging
import pickle
from datetime import datetime
from emmaa.util import get_s3_client, make_date_str
from emmaa.db import get_db
from emmaa.queries import Query


logger = logging.getLogger(__name__)


model_manager_cache = {}


class QueryManager(object):
    def __init__(self, db_name='primary', model_managers=None):
        self.db = get_db(db_name)
        self.model_managers = model_managers if model_managers else []

    def answer_immediate_query(self, user_email, query_dict, model_names, subscribe):
        query = Query._from_json(query_dict)
        query_dict = query.to_json()
        db.put_queries(user_email, query_dict, model_names, subscribe)
        # Check if the query has already been answered for any of given models and
        # retrieve the results from database.
        saved_results = db.get_results_from_query(query_dict, model_names)
        checked_models = {res[0] for res in saved_results}
        if checked_models == set(model_names):
            return format_results(saved_results)
        # Run answer queries mechanism for models for which result was not found.
        new_results = []
        new_date = datetime.now()
        for model_name in model_names:
            if model_name not in checked_models:
                mm = get_model_manager(model_name)
                response = mm.answer_query(query)
                new_results.append((model_name, query_dict, response, new_date))
                if subscribe:
                    db.put_results(model_name, [(query_dict, response)])
        all_results = saved_results + new_results
        return format_results(all_results)
    
    def get_model_manager(self, model_name):
        # Try get model manager from class attributes or load from s3.
        for mm in self.model_managers:
            if mm.model.name == model_name:
                return mm
        return load_model_manager_from_s3(model_name)

    def answer_registered_queries(self, model_name):
        """Retrieve queries registered on database for a given model, answer them,
        and put results to a database.
        """
        model_manager = self.get_model_manager(model_name)
        query_dicts = db.get_queries(model_name)
        queries = [Query._from_json(json) for json in query_dicts]
        results = model_manager.answer_queries(queries)
        db.put_results(model_name, results)


def get_registered_queries(user_email, db_name='primary'):
    """Get formatted results to queries registered by user."""
    db = get_db(db_name)
    results = db.get_results(user_email)
    return format_results(results)


def format_results(results):
    """Format db output to a standard json structure."""
    formatted_results = []
    for result in results:
        formatted_result = {}
        formatted_result['model'] = result[0]
        formatted_result['query'] = result[1]
        response_json = result[2]
        response_hashes = [key for key in response_json.keys()]
        sentence_link_pairs = response_json[response_hashes[0]]
        response_list = []
        for ix, (sentence, link) in enumerate(sentence_link_pairs):
            if ix > 0:
                response_list.append('<br>')
            response_list.append(
                f'<a href="{link}" target="_blank" '
                f'class="status-link">{sentence}</a>')
        response = ''.join(response_list)
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
