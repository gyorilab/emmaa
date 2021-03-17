import logging
from emmaa.util import _get_flask_app
from emmaa.subscription.email_util import generate_unsubscribe_link
from emmaa.answer_queries import make_reports_from_results


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


def get_user_delta(db, user_email, domain='emmaa.indra.bio'):
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