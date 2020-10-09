import time
import random

from nose.plugins.attrib import attr
from nose.tools import with_setup

from emmaa.db import Query, Result, User, UserQuery
from emmaa.queries import Query as QueryObject, PathProperty
from emmaa.tests.db_setup import _get_test_db, setup_function, \
    teardown_function


test_query_jsons = [{'type': 'path_property', 'path': {'type': 'Activation',
                     'subj': {'type': 'Agent', 'name': 'BRAF'},
                     'obj': {'type': 'Agent', 'name': 'ERK'}}},
                    {'type': 'path_property', 'path':
                    {'type': 'Phosphorylation',
                     'enz': {'type': 'Agent', 'name': 'ERK'},
                     'sub': {'type': 'Agent', 'name': 'MEK'}}}]

test_queries = [QueryObject._from_json(qj) for qj in test_query_jsons]


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_instantiation():
    db = _get_test_db()
    assert db
    return


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_put_queries():
    db = _get_test_db()
    db.put_queries('joshua', 1, test_queries[0], ['aml', 'luad'])
    with db.get_session() as sess:
        queries = sess.query(Query).all()
    assert len(queries) == 2, len(queries)
    # Not logged in user
    db.put_queries(None, None, test_queries[1], ['aml'])
    with db.get_session() as sess:
        queries = sess.query(Query).all()
    assert len(queries) == 3, len(queries)


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_get_queries():
    db = _get_test_db()
    for query in test_queries:
        db.put_queries('joshua', 1, query, ['aml', 'luad'])
        db.put_queries('test_user', 2, query, ['aml'])
    # We should only get distinct queries, independent of number of users
    queries = db.get_queries('aml')
    assert len(queries) == 2, len(queries)
    assert all(isinstance(query, PathProperty) for query in queries)
    queries = db.get_queries('luad')
    assert len(queries) == 2, len(queries)
    assert all(isinstance(query, PathProperty) for query in queries)


def _get_random_result():
    return random.choice(
        [{'12': [['This is fine.', '']]}, {'34': [['This is not ok.', '']]}])


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_put_results():
    db = _get_test_db()
    db.put_queries('joshua', 1, test_queries[0], ['aml', 'luad'])
    queries = db.get_queries('aml')
    results = [(query, '', _get_random_result())
               for query in queries]
    db.put_results('aml', results)
    with db.get_session() as sess:
        db_results = sess.query(Result).all()
    assert len(db_results) == len(results)


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_get_results():
    db = _get_test_db()
    models = ['aml', 'luad']

    # Fill up the database.
    for query in test_queries:
        db.put_queries('joshua', 1, query, models)
    for model in models:
        db.put_results(model, [(query, 'pysb', _get_random_result())
                               for query in test_queries])

    # Try to get the results.
    results = db.get_results('joshua')
    assert len(results) == len(test_queries)*len(models)
    assert all(isinstance(result, tuple) for result in results)
    assert all(result[0] in models for result in results)
    assert any(results[0][1].matches(q) for q in test_queries)
    assert all(isinstance(result[2], str) for result in results)
    assert all(isinstance(result[3], dict) for result in results)


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_get_latest_results():
    db = _get_test_db()
    models = ['aml', 'luad']

    # Fill up the database.
    for query in test_queries:
        db.put_queries('joshua', 1, query, models)
    for model in models:
        db.put_results(model, [(query, 'pysb', _get_random_result())
                               for query in test_queries])

    # Add the same statements over again
    time.sleep(10)
    for model in models:
        db.put_results(model, [(query, 'pysb', _get_random_result())
                               for query in test_queries])

    # Try to get the results. Make sure we only get the one set.
    results = db.get_results('joshua')
    assert len(results) == len(test_queries)*len(models), len(results)
    assert all(isinstance(result, tuple) for result in results)
    assert all(result[0] in models for result in results)
    assert any(results[0][1].matches(q) for q in test_queries)
    assert all(isinstance(result[2], str) for result in results)
    assert all(isinstance(result[3], dict) for result in results)


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_get_subscribed_queries():
    db = _get_test_db()
    db.put_queries('test@test.com', 1, test_queries[0], ['aml'], True)
    db.put_queries('test@test.com', 1, test_queries[1], ['aml'], False)
    # Only return queries for which subscription is True
    queries = db.get_subscribed_queries('test@test.com')
    assert len(queries) == 1
    assert queries[0][2] == test_queries[0].get_hash_with_model('aml')


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_get_subscribed_users():
    db = _get_test_db()
    db.put_queries('test1@test.com', 1, test_queries[0], ['aml'], True)
    db.put_queries('test2@test.com', 2, test_queries[1], ['aml'], False)
    # Only return users that subscribed for something
    emails = db.get_subscribed_users()
    assert len(emails) == 1
    assert emails[0] == 'test1@test.com'


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_update_email_subscription():
    db = _get_test_db()
    db.put_queries('test1@test.com', 1, test_queries[0], ['aml'], True)
    qh = test_queries[0].get_hash_with_model('aml')
    with db.get_session() as sess:
        q = sess.query(UserQuery.subscription).filter(
            UserQuery.user_id == 1, UserQuery.query_hash == qh)
    assert [q[0] for q in q.all()][0]  # True
    db.update_email_subscription('test1@test.com', [qh], False)
    with db.get_session() as sess:
        q = sess.query(UserQuery.subscription).filter(
            UserQuery.user_id == 1,
            UserQuery.query_hash == test_queries[0].get_hash_with_model('aml'))
    assert not [q[0] for q in q.all()][0]  # new subscription status is False


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_get_number_results():
    db = _get_test_db()
    db.put_queries('test@test.com', 1, test_queries[0], ['aml'])
    db.put_results('aml', [(test_queries[0], 'pysb', _get_random_result())])
    time.sleep(1)
    db.put_results('aml', [(test_queries[0], 'pysb', _get_random_result())])
    time.sleep(1)
    db.put_results('aml', [(test_queries[0], 'pysb', _get_random_result())])
    qh = test_queries[0].get_hash_with_model('aml')
    assert db.get_number_of_results(qh, 'pysb') == 3


@with_setup(setup_function, teardown_function)
@attr('nonpublic')
def test_get_all_result_hashes_and_delta():
    db = _get_test_db()
    db.put_queries('test@test.com', 1, test_queries[0], ['aml'])
    qh = test_queries[0].get_hash_with_model('aml')
    # If there are no older results, all hashes is None
    assert db.get_all_result_hashes(qh, 'pysb') is None
    db.put_results('aml', [(test_queries[0], 'pysb', {'1234': 'result'})])
    assert db.get_all_result_hashes(qh, 'pysb') == {'1234'}
    # First result is not delta
    results = db.get_results_from_hashes([qh])
    assert results[0][4] == [], results[0]
    # All hashes keeps growing
    time.sleep(1)
    db.put_results('aml', [(test_queries[0], 'pysb', {'345': 'other'})])
    assert db.get_all_result_hashes(qh, 'pysb') == {'1234', '345'}
    results = db.get_results_from_hashes([qh])
    assert results[0][4] == ['345'], results[0]
    # When we go to previous result, it's not delta
    time.sleep(1)
    db.put_results('aml', [(test_queries[0], 'pysb', {'1234': 'result'})])
    assert db.get_all_result_hashes(qh, 'pysb') == {'1234', '345'}
    results = db.get_results_from_hashes([qh])
    assert results[0][4] == [], results[0]
