import logging
import time
from emmaa.util import _get_flask_app, _make_delta_msg, EMMAA_BUCKET_NAME, \
    get_credentials, update_status
from emmaa.subscription.email_util import generate_unsubscribe_link
from emmaa.answer_queries import make_reports_from_results
from emmaa.model import load_config_from_s3, get_model_stats


logger = logging.getLogger(__name__)


class EmailHtmlBody(object):
    app = _get_flask_app()

    def __init__(self, domain='emmaa.indra.bio',
                 template_path='email_unsub/email_body.html'):
        self.template = self.app.jinja_env.get_template(template_path)
        self.domain = domain
        self.static_tab_link = f'https://{domain}/query?tab=static'
        self.dynamic_tab_link = f'https://{domain}/query?tab=dynamic'
        self.open_tab_link = f'https://{domain}/query?tab=open'

    def render(self, static_query_deltas, open_query_deltas,
               dynamic_query_deltas, unsub_link):
        """Provided the delta json objects, render HTML to put in email body

        Parameters
        ----------
        static_query_deltas : json
            A list of lists that names which queries have updates. Expected
            structure:
            [(english_query, detailed_query_link, model, model_type)]
        dynamic_query_deltas : list[
            A list of lists that names which queries have updates. Expected
            structure:
            [(english_query, model, model_type)]
        unsub_link : str

        Returns
        -------
        html
            An html string rendered from the associated jinja2 template
        """
        if not static_query_deltas and not open_query_deltas and \
                not dynamic_query_deltas:
            raise ValueError('No query deltas provided')
        # Todo consider generating unsubscribe link here, will probably have
        #  to solve import loops for that though
        return self.template.render(
            static_tab_link=self.static_tab_link,
            static_query_deltas=static_query_deltas,
            open_tab_link=self.open_tab_link,
            open_query_deltas=open_query_deltas,
            dynamic_tab_link=self.dynamic_tab_link,
            dynamic_query_deltas=dynamic_query_deltas,
            unsub_link=unsub_link
        ).replace('\n', '')


def get_user_query_delta(db, user_email, domain='emmaa.indra.bio'):
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
    results = db.get_results(user_email, latest_order=1)

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
    email_html = EmailHtmlBody()
    if static_results_delta or open_results_delta or dynamic_results_delta:
        return email_html.render(
            static_query_deltas=static_results_delta,
            open_query_deltas=open_results_delta,
            dynamic_query_deltas=dynamic_results_delta,
            unsub_link=link
        )
    else:
        return ''


def get_model_deltas(model_name, test_corpora, date, bucket=EMMAA_BUCKET_NAME):
    """Get deltas from model and test stats for further use in tweets and
    email notifications.

    Parameters
    ----------
    model_name : str
        A name of the model to get the updates for.
    test_corpora : list[str]
        A list of test corpora names to get the test updates for.
    date : str
        A date for which the updates should be generated.

    Returns
    -------
    deltas : dict
        A dictionary containing the deltas for the given model and test
        corpora.
    """
    deltas = {}
    model_stats, _ = get_model_stats(model_name, 'model', date=date)
    test_stats_by_corpus = {}
    for test_corpus in test_corpora:
        test_stats, _ = get_model_stats(model_name, 'test', tests=test_corpus,
                                        date=date)
        if not test_stats:
            logger.info(f'Could not find test stats for {test_corpus}')
        test_stats_by_corpus[test_corpus] = test_stats
    if not model_stats or not test_stats_by_corpus:
        logger.warning('Stats are not found, cannot generate deltas')
        return deltas
    deltas['model_name'] = model_name
    deltas['date'] = date
    # Model deltas
    stmts_delta = model_stats['model_delta']['statements_hashes_delta']
    paper_delta = model_stats['paper_delta']['raw_paper_ids_delta']
    new_papers = len(paper_delta['added'])
    deltas['stmts_delta'] = stmts_delta
    deltas['new_papers'] = new_papers
    # Test deltas
    deltas['tests'] = {}
    for test_corpus, test_stats in test_stats_by_corpus.items():
        test_deltas = {}
        test_name = None
        test_data = test_stats['test_round_summary'].get('test_data')
        if test_data:
            test_name = test_data.get('name')
        test_deltas['name'] = test_name
        test_deltas['passed'] = {}
        for k, v in test_stats['tests_delta'].items():
            if k == 'applied_hashes_delta':
                applied_delta = v
                test_deltas['applied_tests'] = applied_delta
            else:
                mc_type = k
                passed_delta = v['passed_hashes_delta']
                test_deltas['passed'][mc_type] = passed_delta
        deltas['tests'][test_corpus] = test_deltas
    return deltas


def get_all_update_messages(deltas, is_tweet=False):
    """Get all messages for model deltas that can be further used in tweets and
    email notifications.

    Parameters
    ----------
    deltas : dict
        A dictionary containing deltas for a model and its test results
        returned by get_model_deltas function.

    is_tweet : bool
        Whether messages are generated for Twitter (used to determine the
        formatting of model types).

    Returns
    -------
    msgs : list[str]
        A list of individual string messages that can be tweeted or emailed to
        user.
    """
    msg_dicts = []
    model_name = deltas['model_name']
    date = deltas['date']
    # Model message
    stmts_delta = deltas.get('stmts_delta')
    new_papers = deltas.get('new_papers')
    stmts_msg = _make_delta_msg(model_name, 'stmts', stmts_delta,
                                date, new_papers=new_papers, is_tweet=is_tweet)
    if stmts_msg:
        logger.info(stmts_msg['message'])
        msg_dicts.append(stmts_msg)
    # Tests messages
    for test_corpus, test_delta in deltas['tests'].items():
        applied_delta = test_delta.get('applied_tests')
        test_name = test_delta.get('name')
        applied_msg = _make_delta_msg(
            model_name, 'applied_tests', applied_delta, date,
            test_corpus=test_corpus, test_name=test_name, is_tweet=is_tweet)
        if applied_msg:
            logger.info(applied_msg['message'])
            msg_dicts.append(applied_msg)
        for mc_type in test_delta.get('passed', {}):
            passed_delta = test_delta['passed'][mc_type]
            passed_msg = _make_delta_msg(
                model_name, 'passed_tests', passed_delta,
                date, mc_type, test_corpus=test_corpus,
                test_name=test_name, is_tweet=is_tweet)
            if passed_msg:
                logger.info(passed_msg['message'])
                msg_dicts.append(passed_msg)
    return msg_dicts


def tweet_deltas(deltas, twitter_cred):
    """Tweet the model updates. This function requires Twitter credentials
    to be stored as AWS SSM parameters and the key to be configured in model
    config.

    Parameters
    ----------
    deltas : dict
        A dictionary containing deltas for a model and its test results
        returned by get_model_deltas function.
    """
    msgs = get_all_update_messages(deltas, is_tweet=True)
    for msg in msgs:
        update_status(msg['message'], twitter_cred)
        time.sleep(1)
    logger.info('Done tweeting')


def model_update_notify(model_name, test_corpora, date, db,
                        bucket=EMMAA_BUCKET_NAME):
    # Find where to send notifications (Twitter, user emails)
    config = load_config_from_s3(model_name, bucket)
    twitter_key = config.get('twitter')
    twitter_cred = get_credentials(twitter_key)

    users = db.get_model_users(model_name)

    if not twitter_cred and not users:
        logger.info('No Twitter account and no users subscribed '
                    'to this model, not generating deltas')
        return

    # Get deltas
    deltas = get_model_deltas(
        model_name, test_corpora, date, bucket=bucket)

    # Tweet if configured
    if twitter_cred:
        tweet_deltas(deltas)

    if users:
        msg_dicts = get_all_update_messages(deltas, is_tweet=False)
        email_str = '\n'.join([msg['message'] for msg in msg_dicts])
