import logging
import time
import os
from collections import Counter
from datetime import datetime, timedelta

from emmaa.util import _get_flask_app, _make_delta_msg, EMMAA_BUCKET_NAME, \
    get_credentials, update_status, FORMATTED_TYPE_NAMES
from emmaa.subscription.email_util import generate_unsubscribe_link
from emmaa.subscription.email_service import send_email, \
    notifications_sender_default, notifications_return_default
from emmaa.model import load_config_from_s3, get_model_stats
from emmaa.db import get_db


logger = logging.getLogger(__name__)
indra_bio_ARN = os.environ.get('INDRA_BIO_ARN')


class EmailHtmlBody(object):
    """Parent class for email body."""
    app = _get_flask_app()

    def __init__(self, template_path):
        self.template = self.app.jinja_env.get_template(template_path)


class QueryEmailHtmlBody(EmailHtmlBody):
    """Email body for query notifications."""
    def __init__(self, domain='emmaa.indra.bio',
                 template_path='email_unsub/email_body.html'):
        super().__init__(template_path)
        self.domain = domain
        self.static_tab_link = f'https://{domain}/query?tab=static'
        self.dynamic_tab_link = f'https://{domain}/query?tab=dynamic'
        self.open_tab_link = f'https://{domain}/query?tab=open'

    def render(self, static_query_deltas, open_query_deltas,
               dynamic_query_deltas, unsub_link):
        """Provided the delta json objects, render HTML to put in email body.

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
            A link to unsubscribe page.

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


class ModelDeltaEmailHtmlBody(EmailHtmlBody):
    """Email body for model updates."""
    def __init__(self, template_path='email_unsub/model_email_body.html'):
        super().__init__(template_path)

    def render(self, msg_dicts, unsub_link):
        """Provided pregenerated msg_dicts render HTML to put in email body.

        Parameters
        ----------
        msg_dicts : list[dict]
            A list of dictionaries containing parts of messages to be added to
            email. Each dictionary has the following keys: 'url', 'start',
            'delta_part', 'middle', 'message'.
        unsub_link : str
            A link to unsubscribe page.

        Returns
        -------
        html
            An html string rendered from the associated jinja2 template
        """
        return self.template.render(
            msg_dicts=msg_dicts,
            unsub_link=unsub_link
        )


def get_user_query_delta(db, user_email, domain='emmaa.indra.bio'):
    """Produce a report for all query results per user in a given format

    Parameters
    ----------
    db : emmaa.db.EmmaaDatabaseManager
        An instance of a database manager to use.
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


def _detailed_page_link(domain, model_name, model_type, query_hash):
    # example:
    # https://emmaa.indra.bio/query/aml/?model_type=pysb&query_hash
    # =4911955502409811&order=1
    return f'https://{domain}/query/{model_name}?model_type=' \
           f'{model_type}&query_hash={query_hash}&order=1'


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
    email_html = QueryEmailHtmlBody()
    if static_results_delta or open_results_delta or dynamic_results_delta:
        return email_html.render(
            static_query_deltas=static_results_delta,
            open_query_deltas=open_results_delta,
            dynamic_query_deltas=dynamic_results_delta,
            unsub_link=link
        )
    else:
        return ''


def get_model_deltas(model_name, date, model_stats, test_stats_by_corpus):
    """Get deltas from model and test stats for further use in tweets and
    email notifications.

    Parameters
    ----------
    model_name : str
        A name of the model to get the updates for.
    date : str
        A date for which the updates should be generated. The
        format should be "YYYY-MM-DD".
    model_stats : dict
        A dictionary containing the stats for the given model.
    test_stats_by_corpus : dict
        A dictionary of test statistics keyed by test corpus name.

    Returns
    -------
    deltas : dict
        A dictionary containing the deltas for the given model and test
        corpora.
    """
    # Model deltas
    stmts_delta = model_stats['model_delta']['statements_hashes_delta']
    paper_delta = model_stats['paper_delta']['raw_paper_ids_delta']
    new_papers = len(paper_delta['added'])

    # Test deltas
    deltas = {
        'model_name': model_name,
        'date': date,
        'stmts_delta': stmts_delta,
        'new_papers': new_papers,
        'tests': {}
    }
    for test_corpus, test_stats in test_stats_by_corpus.items():
        if test_stats is None:
            logger.info(f"No test stats for {test_corpus}")
            continue

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
    msg_dicts : list[dict]
        A list of individual message dictionaries that can be used for tweets
        or email notifications.
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


def tweet_deltas(deltas, twitter_cred, verbose=False):
    """Tweet the model updates.

    Parameters
    ----------
    deltas : dict
        A dictionary containing deltas for a model and its test results
        returned by get_model_deltas function.
    twitter_cred : dict
        A dictionary containing consumer_token, consumer_secret, access_token,
        and access_secret for a model Twitter account.
    verbose : bool
        If True, the return from `tweepy.Client.create_tweet` will be printed
    """
    msgs = get_all_update_messages(deltas, is_tweet=True)
    for msg in msgs:
        res = update_status(msg['message'], twitter_cred)
        if verbose:
            print(res)
        time.sleep(1)
    if msgs:
        logger.info(f'Done tweeting {len(msgs)} messages')
    else:
        logger.info('No tweets to send')


def make_model_html_email(msg_dicts, email, domain='emmaa.indra.bio'):
    """Render html file for model notification email."""
    unsub_link = generate_unsubscribe_link(email=email, domain=domain)
    email_html = ModelDeltaEmailHtmlBody()
    return email_html.render(msg_dicts, unsub_link=unsub_link)


def get_all_stats(model_name, test_corpora, date):
    """Get all stats for a model and its test corpora.

    Parameters
    ----------
    model_name : str
        A name of the model to get the updates for.
    test_corpora : list[str]
        A list of test corpora names to get the test updates for.
    date : str
        A date for which the updates should be generated. The
        format should be "YYYY-MM-DD".

    Returns
    -------
    model_stats : dict
        A dictionary containing the stats for the given model.
    test_stats_by_corpus : dict
        A dictionary of test statistics keyed by test corpus name.
    """
    model_stats, _ = get_model_stats(model_name, 'model', date=date)
    test_stats_by_corpus = {}
    for test_corpus in test_corpora:
        test_stats, _ = get_model_stats(model_name, 'test', tests=test_corpus,
                                        date=date)
        if not test_stats:
            logger.info(
                f"Could not find test stats for {test_corpus} for date {date}"
            )
        test_stats_by_corpus[test_corpus] = test_stats
    return model_stats, test_stats_by_corpus


def update_path_counts(model_name, date, test_stats_by_corpus):
    """Combine path counts from all test corpora and update in the database."""
    db = get_db('stmt')
    path_count_dict = Counter()
    for test_corpus, test_stats in test_stats_by_corpus.items():
        stmt_counts = test_stats['test_round_summary'].get(
            'path_stmt_counts', [])
        path_count_dict += Counter(dict(stmt_counts))
    path_count_dict = dict(path_count_dict)
    db.update_statements_path_counts(model_name, date, path_count_dict)


def model_update_notify(model_name, test_corpora, date, db,
                        bucket=EMMAA_BUCKET_NAME):
    """This function finds delta for a given model and sends updates via
    Twitter posts and email notifications.

    Parameters
    ----------
    model_name : str
        A name of EMMAA model.
    test_corpora : list[str]
        A list of test corpora names to get test stats.
    date : str
        A date for which to get stats for.
    db : emmaa.db.EmmaaDatabaseManager
        An instance of a database manager to use.
    bucket : str
        A name of S3 bucket where corresponding stats files are stored.
    """
    # Find where to send notifications (Twitter, user emails)
    config = load_config_from_s3(model_name, bucket)
    twitter_cred = None
    twitter_key = config.get('twitter')
    if twitter_key:
        twitter_cred = get_credentials(twitter_key)

    users = db.get_model_users(model_name)

    # Get all the stats from S3
    model_stats, test_stats_by_corpus = get_all_stats(
        model_name, test_corpora, date)

    if not model_stats or not test_stats_by_corpus:
        logger.warning('Stats are not found, cannot generate deltas')
        return

    # Update path counts in the statements database
    update_path_counts(model_name, date, test_stats_by_corpus)

    # We only need the next steps if there are subscribers or Twitter account
    if not twitter_cred and not users:
        logger.info('No Twitter account and no users subscribed '
                    'to this model, not generating deltas')
        return

    # Get deltas
    deltas = get_model_deltas(
        model_name, date, model_stats, test_stats_by_corpus)

    # Tweet if configured
    if twitter_cred:
        tweet_deltas(deltas, twitter_cred)

    # Send emails if there are subscribed users
    if users:
        msg_dicts = get_all_update_messages(deltas, is_tweet=False)
        if msg_dicts:
            str_email = '\n'.join([msg['message'] for msg in msg_dicts])
            full_name = config.get('human_readable_name', model_name)
            subject_line = f'Updates to the {full_name} EMMAA model'
            for user_email in users:
                html_email = make_model_html_email(msg_dicts, user_email)
                res = send_email(sender=notifications_sender_default,
                                 recipients=[user_email],
                                 subject=subject_line,
                                 body_text=str_email,
                                 body_html=html_email,
                                 source_arn=indra_bio_ARN,
                                 return_email=notifications_return_default,
                                 return_arn=indra_bio_ARN
                                 )
