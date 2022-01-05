from datetime import datetime
from nose.plugins.attrib import attr
from emmaa.subscription.notifications import make_str_report_per_user, \
    make_html_report_per_user, get_user_query_delta, \
    make_reports_from_results, get_all_update_messages
from emmaa.tests.db_setup import _get_test_db, setup_query_db, \
    teardown_query_db
from emmaa.tests.test_answer_queries import query_object, test_email, \
    test_response, fail_response, query_not_appl, open_query, dyn_query
from emmaa.util import _make_delta_msg


def setup_module():
    setup_query_db()


def teardown_module():
    teardown_query_db()


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


def test_delta_msg():
    # No message when no delta
    msg = _make_delta_msg('test', 'stmts', {'added': []}, '2020-01-01',
                          new_papers=2)
    assert not msg
    # No message with no new papers
    msg = _make_delta_msg('test', 'stmts', {'added': [1234, 2345]},
                          '2020-01-01', new_papers=None)
    assert not msg, msg
    # New statements with new papers message
    msg = _make_delta_msg('test', 'stmts', {'added': [1234, 2345]},
                          '2020-01-01', new_papers=5)
    assert set(msg.keys()) == {
        'message', 'start', 'middle', 'delta_part', 'url'}
    assert msg['message'] == (
        'Today I read 5 new publications and learned 2 new mechanisms. See '
        'https://emmaa.indra.bio/dashboard/test?tab=model&date='
        '2020-01-01#addedStmts for more details.'), msg['message']
    # New applied tests message
    msg = _make_delta_msg('test', 'applied_tests', {'added': [1234, 2345]},
                          '2020-01-01', test_corpus='simple_tests',
                          test_name='Simple tests corpus')
    assert set(msg.keys()) == {
        'message', 'start', 'middle', 'delta_part', 'url'}
    assert msg['message'] == (
        'Today I applied 2 new tests in the Simple tests corpus. '
        'See https://emmaa.indra.bio/dashboard/test?'
        'tab=tests&test_corpus=simple_tests&date=2020-01-01'
        '#newAppliedTests for more details.'), msg['message']
    # New passed tests message
    msg = _make_delta_msg('test', 'passed_tests', {'added': [1234, 2345]},
                          '2020-01-01', 'pysb', test_corpus='simple_tests',
                          test_name='Simple tests corpus', is_tweet=True)
    assert set(msg.keys()) == {
        'message', 'start', 'middle', 'delta_part', 'url'}
    assert msg['message'] == (
        'Today I explained 2 new observations in the Simple tests '
        'corpus with my @PySysBio model. See '
        'https://emmaa.indra.bio/dashboard/test?tab=tests'
        '&test_corpus=simple_tests&date=2020-01-01#newPassedTests '
        'for more details.'), msg['message']


def test_get_all_messages():
    deltas = {
        'model_name': 'test',
        'date': '2020-01-01',
        'stmts_delta': {'added': ['-13855132444206450', '2874381165909177'],
                        'removed': []},
        'new_papers': 2,
        'tests': {'simple_tests': {
            'name': None,
            'passed': {'pysb': {'added': ['34500484183886742'], 'removed': []},
                       'pybel': {'added': ['34500484183886742'],
                                 'removed': []},
                       'signed_graph': {'added': ['34500484183886742'],
                                        'removed': []},
                       'unsigned_graph': {'added': ['34500484183886742'],
                                          'removed': []}},
            'applied_tests': {'added': ['34500484183886742'], 'removed': []}}}}
    msg_dicts = get_all_update_messages(deltas)
    assert len(msg_dicts) == 6
    for msg_dict in msg_dicts:
        assert set(msg_dict.keys()) == {
            'message', 'start', 'middle', 'delta_part', 'url'}
