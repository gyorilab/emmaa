from datetime import datetime
from nose.plugins.attrib import attr
from emmaa.subscription.notifications import make_str_report_per_user, \
    make_html_report_per_user, get_user_query_delta, make_reports_from_results
from emmaa.tests.db_setup import _get_test_db, setup_function, \
    teardown_function
from emmaa.tests.test_answer_queries import query_object, test_email, \
    test_response, fail_response, query_not_appl, open_query, dyn_query


def setup_module():
    setup_function()


def teardown_module():
    teardown_function()


@attr('nonpublic')
def test_user_query_delta():
    db = _get_test_db()
    # Using results from db
    db.put_queries(test_email, 1, query_object, ['test'], subscribe=True)
    db.put_results('test', [(query_object, 'pysb', test_response)])
    db.put_results('test', [(query_object, 'pysb', query_not_appl)])
    str_rep, html_rep = get_user_query_delta(db, user_email=test_email)
    assert str_rep, print(str_rep)
    assert html_rep, print(html_rep)
    assert '</html>' in html_rep
    assert '</body>' in html_rep
    assert 'pysb' in html_rep
    assert 'unsubscribe' in html_rep


@attr('nonpublic')
def test_make_reports():
    date = datetime.now()
    results = [
        ('test', query_object, 'pysb', test_response, {'3801854542'}, date),
        ('test', query_object, 'signed_graph', fail_response, {}, date),
        ('test', query_object, 'unsigned_graph', test_response, {}, date),
        ('test', open_query, 'pysb', test_response, {'3801854542'}, date),
        ('test', dyn_query, 'pysb', query_not_appl, {'2413475507'}, date)]
    static_rep, open_rep, dyn_rep = make_reports_from_results(results)
    assert static_rep
    assert open_rep
    assert dyn_rep
    str_rep = make_str_report_per_user(static_rep, open_rep, dyn_rep)
    assert str_rep
    assert 'Updates to your static queries:' in str_rep
    assert 'Updates to your open queries:' in str_rep
    assert 'Updates to your dynamic queries:' in str_rep
    html_rep = make_html_report_per_user(static_rep, open_rep, dyn_rep,
                                         test_email)
    assert html_rep
    assert ('Updates to your <a href="https://emmaa.indra.bio/query?'
            'tab=static">static') in html_rep
    assert ('Updates to your <a href="https://emmaa.indra.bio/query?'
            'tab=open">open') in html_rep
    assert ('Updates to your <a href="https://emmaa.indra.bio/query?'
            'tab=dynamic">dynamic') in html_rep
