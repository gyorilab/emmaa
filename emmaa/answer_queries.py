import logging
from datetime import datetime
from copy import deepcopy

from emmaa.model_tests import load_model_manager_from_s3
from emmaa.db import get_db
from emmaa.util import make_date_str, find_latest_s3_file, EmailHtmlBody, \
    EMMAA_BUCKET_NAME, FORMATTED_TYPE_NAMES
from emmaa.subscription.email_util import generate_unsubscribe_link


logger = logging.getLogger(__name__)


model_manager_cache = {}


email_html = EmailHtmlBody()


class QueryManager(object):
    """Manager to run queries and interact with the database.

    Parameters
    ----------
    db : emmaa.db.EmmaaDatabaseManager
        An instance of a database manager to use.
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
            self, user_email, user_id, query, model_names, subscribe,
            use_kappa=False, bucket=EMMAA_BUCKET_NAME):
        """This method first tries to find saved result to the query in the
        database and if not found, runs ModelManager method to answer query."""
        query_type = query.get_type()
        # Retrieve query-model hashes
        query_hashes = [
            query.get_hash_with_model(model) for model in model_names]
        # Store query in the database for future reference.
        self.db.put_queries(user_email, user_id, query, model_names, subscribe)
        # Check if the query has already been answered for any of given models
        # and retrieve the results from database.
        saved_results = self.db.get_results_from_query(query, model_names)
        if not saved_results:
            saved_results = []
        checked_models = {res[0] for res in saved_results}
        # If the query was answered for all models before, return the hashes.
        if checked_models == set(model_names):
            return {query_type: query_hashes}
        # Run queries mechanism for models for which result was not found.
        new_results = []
        new_date = datetime.now()
        for model_name in model_names:
            if model_name not in checked_models:
                results_to_store = []
                mm = self.get_model_manager(model_name)
                response_list = mm.answer_query(
                    query, use_kappa=use_kappa, bucket=bucket)
                for (mc_type, response, paths) in response_list:
                    results_to_store.append((query, mc_type, response))
                self.db.put_results(model_name, results_to_store)
        return {query_type: query_hashes}

    def answer_registered_queries(self, model_name, use_kappa=False,
                                  bucket=EMMAA_BUCKET_NAME):
        """Retrieve and asnwer registered queries

        Retrieve queries registered on database for a given model,
        answer them, calculate delta between results and put results to a
        database.

        Parameters
        ----------
        model_name : str
            The name of the model
        use_kappa : bool
            If True, use kappa modeling when answering the dynamic query
        bucket : str
            The bucket to save the results to
        """
        model_manager = self.get_model_manager(model_name)
        queries = self.db.get_queries(model_name)
        logger.info(f'Found {len(queries)} queries for {model_name} model.')
        # Only do the following steps if there are queries for this model
        if queries:
            results = model_manager.answer_queries(
                queries, use_kappa=use_kappa, bucket=bucket)
            new_results = [(model_name, result[0], result[1], result[2], '')
                           for result in results]
            self.db.put_results(model_name, results)

    def get_registered_queries(self, user_email, query_type='path_property'):
        """Get formatted results to queries registered by user."""
        results = self.db.get_results(user_email, query_type=query_type)
        return format_results(results, query_type)

    def retrieve_results_from_hashes(
            self, query_hashes, query_type='path_property', latest_order=1):
        """Retrieve results from a db given a list of query-model hashes."""
        results = self.db.get_results_from_hashes(
            query_hashes, latest_order=latest_order)
        return format_results(results, query_type)

    def get_user_query_delta(self, user_email, domain='emmaa.indra.bio'):
        """Produce a report for all query results per user in a given format

        Parameters
        ----------
        user_email : str
            The email of the user for which to get the report for
        domain : str
            The domain name for the unsubscibe link in the html
            report. Default: "emmaa.indra.bio".

        Returns
        -------
        tuple(str, html_str)
            A tuple with (str report, html report)
        """
        logger.info(f'Finding query delta for {user_email}')
        # Get results of user's query
        results = self.db.get_results(user_email, latest_order=1)

        # Get the query deltas
        static_results_delta, open_results_delta, dynamic_results_delta = \
            make_reports_from_results(results, domain=domain)
        # Make text report
        str_report = make_str_report_per_user(static_results_delta,
                                              open_results_delta,
                                              dynamic_results_delta)
        str_report = str_report if str_report else ''

        # Make html report
        html_report = make_html_report_per_user(static_results_delta,
                                                open_results_delta,
                                                dynamic_results_delta,
                                                user_email,
                                                domain=domain)
        html_report = html_report if html_report else None

        if html_report:
            logger.info(f'Found query delta for {user_email}')
        else:
            logger.info(f'No query delta to report for {user_email}')
        return str_report, html_report

    def get_model_manager(self, model_name):
        # Try get model manager from class attributes or load from s3.
        for mm in self.model_managers:
            if mm.model.name == model_name:
                return mm
        return load_model_manager_from_cache(model_name)


def make_reports_from_results(new_results, domain='emmaa.indra.bio'):
    """Make a report given latest results and queries the results are for.

    Parameters
    ----------
    new_results : list[tuple]
        Latest results as a list of tuples where each tuple has the format
        (model_name, query, mc_type, result_json, date, delta).

    Returns
    -------
    reports : list
        A list of reports on changes for each of the queries.
    """
    processed_query_mc = []
    static_reports = []
    open_reports = []
    dynamic_reports = []
    for model_name, query, mc_type, result_json, delta, _ in new_results:
        if (model_name, query, mc_type) in processed_query_mc:
            continue
        if delta:
            model_type_name = FORMATTED_TYPE_NAMES[
                mc_type] if mc_type else mc_type
            rep = [
                query.to_english(),
                _detailed_page_link(
                    domain,
                    model_name,
                    mc_type,
                    query.get_hash_with_model(
                        model_name)),
                model_name,
                model_type_name
            ]
            # static
            if query.get_type() == 'path_property':
                static_reports.append(rep)
            # open
            elif query.get_type() == 'open_search_query':
                open_reports.append(rep)
            # dynamic
            else:
                # Remove link for dynamic
                _ = rep.pop(1)
                dynamic_reports.append(rep)
        processed_query_mc.append((model_name, query, mc_type))
    return static_reports, open_reports, dynamic_reports


def make_str_report_per_user(static_results_delta, open_results_delta,
                             dynamic_results_delta):
    """Produce a report for all query results per user as a string.

    Parameters
    ----------
    static_results_delta : list
        A list of tuples of query deltas for static queries. Each tuple
        has a format (english_query, link, model, mc_type)
    open_results_delta : list
        A list of tuples of query deltas for open queries. Each tuple
        has a format (english_query, link, model, mc_type)
    dynamic_results_delta : list
        A list of tuples of query deltas for dynamic queries. Each tuple
        has a format (english_query, link, model, mc_type) (no link in
        dynamic_results_delta tuples).

    Returns
    -------
    msg : str
        A message about query deltas.
    """
    if not static_results_delta and not open_results_delta and not \
            dynamic_results_delta:
        logger.info('No delta provided')
        return None
    msg = ''
    if static_results_delta:
        msg += 'Updates to your static queries:\n'
        for english_query, _, model, mc_type in static_results_delta:
            msg += f'{english_query} in {model} using the {mc_type}.\n'
    if open_results_delta:
        msg += 'Updates to your open queries:\n'
        for english_query, _, model, mc_type in open_results_delta:
            msg += f'{english_query} in {model} using the {mc_type}.\n'
    if dynamic_results_delta:
        msg += 'Updates to your dynamic queries:\n'
        for english_query, model, mc_type in dynamic_results_delta:
            msg += f'{english_query} in {model} using the {mc_type}.\n'
    return msg


def make_html_report_per_user(static_results_delta, open_results_delta,
                              dynamic_results_delta, email,
                              domain='emmaa.indra.bio'):
    """Produce a report for all query results per user in an html file.

    Parameters
    ----------
    static_results_delta : list
        A list of tuples of query deltas for static queries. Each tuple
        has a format (english_query, link, model, mc_type)
    open_results_delta : list
        A list of tuples of query deltas for open queries. Each tuple
        has a format (english_query, link, model, mc_type)
    dynamic_results_delta : list
        A list of tuples of query deltas for dynamic queries. Each tuple
        has a format (english_query, link, model, mc_type)
    email : str
        The email of the user to get the results for.
    domain : str
        The domain name for the unsubscibe link in the report. Default:
        "emmaa.indra.bio".

    Returns
    -------
    str
        A string containing an html document
    """
    # Generate unsubscribe link
    link = generate_unsubscribe_link(email=email, domain=domain)

    if static_results_delta or open_results_delta or dynamic_results_delta:
        return email_html.render(
            static_query_deltas=static_results_delta,
            open_query_deltas=open_results_delta,
            dynamic_query_deltas=dynamic_results_delta,
            unsub_link=link
        )
    else:
        return ''


def _detailed_page_link(domain, model_name, model_type, query_hash):
    # example:
    # https://emmaa.indra.bio/query/aml/?model_type=pysb&query_hash
    # =4911955502409811&order=1
    return f'https://{domain}/query/{model_name}?model_type=' \
           f'{model_type}&query_hash={query_hash}&order=1'


def format_results(results, query_type='path_property'):
    """Format db output to a standard json structure."""
    model_types = ['pysb', 'pybel', 'signed_graph', 'unsigned_graph']
    formatted_results = {}
    for result in results:
        model = result[0]
        query = result[1]
        query_hash = query.get_hash_with_model(model)
        if query_hash not in formatted_results:
            formatted_results[query_hash] = {
                'query': query.to_english(),
                'model': model,
                'date': make_date_str(result[5])}
        mc_type = result[2]
        response_json = result[3]
        delta = result[4]
        response = []
        for k, v in response_json.items():
            if isinstance(v, str):
                response = v
            elif isinstance(v, dict):
                if k in delta:
                    new_v = deepcopy(v)
                    new_v['path'] = ('new', new_v['path'])
                    response.append(new_v)
                else:
                    response.append(v)
        if query_type in ['path_property', 'open_search_query']:
            if mc_type == '' and \
                    response == 'Query is not applicable for this model':
                for mt in model_types:
                    formatted_results[query_hash][mt] = ['n_a', response]
            elif isinstance(response, str) and \
                    response == 'Statement type not handled':
                formatted_results[query_hash][mc_type] = ['n_a', response]
            elif isinstance(response, str) and \
                    not response == 'Path found but exceeds search depth':
                formatted_results[query_hash][mc_type] = ['Fail', response]
            else:
                formatted_results[query_hash][mc_type] = ['Pass', response]
        elif query_type == 'dynamic_property':
            if response == 'Query is not applicable for this model':
                formatted_results[query_hash]['result'] = ['n_a', response]
            else:
                res = int(response[0]['sat_rate'] * 100)
                expl = (f'Satisfaction rate is {res}% after '
                        f'{response[0]["num_sim"]} simulations.')
                if res > 50:
                    formatted_results[query_hash]['result'] = ['Pass', expl]
                else:
                    formatted_results[query_hash]['result'] = ['Fail', expl]
                formatted_results[query_hash]['image'] = (
                    response[0]['fig_path'])
    if query_type in ['path_property', 'open_search_query']:
        # Loop through the results again to make sure all model types are there
        for qh in formatted_results:
            for mt in model_types:
                if mt not in formatted_results[qh]:
                    formatted_results[qh][mt] = [
                        'n_a', 'Model type not supported']
    return formatted_results


def load_model_manager_from_cache(model_name, bucket=EMMAA_BUCKET_NAME):
    model_manager = model_manager_cache.get(model_name)
    if model_manager:
        latest_on_s3 = find_latest_s3_file(
            bucket, f'results/{model_name}/model_manager_', '.pkl')
        cached_date = model_manager.date_str
        logger.info(f'Found model manager cached on {cached_date} and '
                    f'latest file on S3 is {latest_on_s3}')
        if cached_date in latest_on_s3:
            logger.info(f'Loaded model manager for {model_name} from cache.')
            return model_manager
    logger.info(f'Loading model manager for {model_name} from S3.')
    model_manager = load_model_manager_from_s3(
        model_name=model_name, bucket=bucket)
    model_manager_cache[model_name] = model_manager
    return model_manager


def answer_queries_from_s3(model_name, db=None, bucket=EMMAA_BUCKET_NAME):
    """Answer registered queries with model manager on s3.

    Parameters
    ----------
    model_name : str
        Name of EmmaaModel to answer queries for.
    db : Optional[emmaa.db.manager.EmmaaDatabaseManager]
        If given over-rides the default primary database.
    """
    mm = load_model_manager_from_s3(model_name=model_name, bucket=bucket)
    qm = QueryManager(db=db, model_managers=[mm])
    qm.answer_registered_queries(model_name)
