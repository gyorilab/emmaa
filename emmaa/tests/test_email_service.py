import os
from time import sleep
from urllib import parse
from datetime import datetime, timedelta, timezone
from nose.plugins.attrib import attr
from emmaa.util import find_latest_emails, get_email_content
from emmaa.subscription.email_service import send_email, \
    notifications_sender_default, close_to_quota_max
from emmaa.subscription.email_util import verify_email_signature, \
    generate_unsubscribe_qs

test_email = 'test@testing.com'
actual_test_receiver = os.environ.get('EMAIL_TEST_RECEIVER')
indra_bio_arn = os.environ.get('INDRA_EMAIL_SOURCE_ARN')
text_body = "This is an email automatically generated from a nosetest"
html_body = """<html>
<head></head>
<body>
  <p>This is an email automatically generated from a nosetest</p>
</body>
</html>"""
html_body_rn = html_body.replace('\n', '\r\n')

options = {'sender': notifications_sender_default,
           'recipients': '',
           'subject': 'Emmaa email nosetest',
           'body_text': text_body,
           'body_html': html_body,
           'source_arn': indra_bio_arn,
           'return_email': 'feedback@indra.bio',
           'return_arn': indra_bio_arn,
           'region': 'us-east-1'}


def test_01_email_options():
    assert indra_bio_arn, 'INDRA_EMAIL_SOURCE_ARN not set in environment'


def _run_sandbox(address):
    options['recipients'] = [address]
    return send_email(**options)


def _get_latest_email_keys(directory, past_minutes=1, w_dt=False):
    return find_latest_emails(email_type=directory,
                              time_delta=timedelta(minutes=past_minutes),
                              w_dt=w_dt)


def _get_latest_feedback_email_content():
    """Return the string containing the contents of the latest feedback
    email"""
    latest_email_key = _get_latest_email_keys('feedback')[-1]
    return get_email_content(latest_email_key)


# Only run this test scarcely, since it will take from the send quota
@attr('nonpublic', 'skip')
def test_actual_email():
    assert not close_to_quota_max(),\
        'Can\'t test email to real address, too close to max quota'
    assert actual_test_receiver, 'EMAIL_TEST_RECEIVER not set in environment'
    options['recipients'] = [actual_test_receiver]
    resp = send_email(**options)
    assert resp['ResponseMetadata']['HTTPStatusCode'] == 200,\
        'HTTP Status Code %d' % resp['ResponseMetadata']['HTTPStatusCode']


@attr('nonpublic')
def test_success():
    # Simulates the recipient's email provider accepting the email.
    address = 'success@simulator.amazonses.com'
    resp = _run_sandbox(address)
    assert resp['ResponseMetadata']['HTTPStatusCode'] == 200,\
        'HTTP Status Code %d' % resp['ResponseMetadata']['HTTPStatusCode']


@attr('nonpublic')
def test_bounce():
    # Simulates the recipient's email provider rejecting your email with an
    # SMTP  550 5.1.1 ("Unknown User") response code.
    address = 'bounce@simulator.amazonses.com'
    dt_sent_email = datetime.utcnow().replace(tzinfo=timezone.utc)
    resp = _run_sandbox(address)
    assert resp['ResponseMetadata']['HTTPStatusCode'] == 200,\
        'HTTP Status Code %d' % resp['ResponseMetadata']['HTTPStatusCode']
    sleep(2)
    feedback_content = _get_latest_feedback_email_content()
    assert 'Content-Description: Delivery Status Notification'\
           in feedback_content
    assert html_body_rn in feedback_content
    assert resp['MessageId'] in feedback_content
    key, dt_feedback = _get_latest_email_keys('feedback', w_dt=True)[-1]
    assert dt_sent_email < dt_feedback


@attr('nonpublic')
def test_auto_response():
    # Tests automated replies, e.g. "I'm Out Of The Office until Monday"
    # Simulates the recipient's email provider accepting the email and
    # sending an automatic response.
    address = 'ooto@simulator.amazonses.com'
    resp = _run_sandbox(address)
    assert resp['ResponseMetadata']['HTTPStatusCode'] == 200,\
        'HTTP Status Code %d' % resp['ResponseMetadata']['HTTPStatusCode']
    # Todo check other or feedback directory on bucket for auto response
    #  message


@attr('nonpublic')
def test_complaint():
    # Simulates the recipient's email provider accepting the email and
    # delivering it to the recipient's inbox, but the recipient marks it as
    # spam. Amazon SES forwards the complaint notification to you.
    address = 'complaint@simulator.amazonses.com'
    resp = _run_sandbox(address)
    assert resp['ResponseMetadata']['HTTPStatusCode'] == 200,\
        'HTTP Status Code %d' % resp['ResponseMetadata']['HTTPStatusCode']
    # Todo check feedback directory on bucket for complaint message


@attr('nonpublic')
def test_suppression_list():
    # Simulates a hard bounce by Amazon SES generating a hard bounce as if
    # the recipient's address is on the Amazon SES suppression list.
    address = 'suppressionlist@simulator.amazonses.com'
    resp = _run_sandbox(address)
    dt_sent_email = datetime.utcnow().replace(tzinfo=timezone.utc)
    assert resp['ResponseMetadata']['HTTPStatusCode'] == 200,\
        'HTTP Status Code %d' % resp['ResponseMetadata']['HTTPStatusCode']
    sleep(2)
    feedback_content = _get_latest_feedback_email_content()
    assert 'Content-Description: Delivery Status Notification'\
           in feedback_content
    assert html_body_rn in feedback_content
    assert resp['MessageId'] in feedback_content
    key, dt_feedback = _get_latest_email_keys('feedback', w_dt=True)[-1]
    assert dt_sent_email < dt_feedback


@attr('nonpublic')
def test_reject():
    # ToDo implement rejection test
    # See here:
    # https://docs.aws.amazon.com/ses/latest/DeveloperGuide/ +
    # mailbox-simulator.html#mailbox-simulator-reject
    pass
    # Todo check feedback directory on bucket for reject message??


def test_unsubscribe_qs_generation():
    days = 1
    expiry = datetime.utcnow() + timedelta(days=days)
    qs = generate_unsubscribe_qs(test_email, days=days)
    qsd = parse.parse_qs(qs)
    assert isinstance(qsd.get('signature'), list)
    assert len(qsd.get('signature')[0]) == 64  # OK for sha256
    assert isinstance(qsd.get('email'), list)
    assert qsd.get('email')[0] == test_email
    assert isinstance(qsd.get('expiration'), list)
    assert expiry - datetime.fromtimestamp(int(qsd.get('expiration')[0])) < \
        timedelta(seconds=1)
    assert verify_email_signature(signature=qsd.get('signature')[0],
                                  email=qsd.get('email')[0],
                                  expiration=qsd.get('expiration')[0])


def test_incorrect_signature():
    # jibberish
    jibberish = 'notasignature'
    jqs = generate_unsubscribe_qs(test_email)
    jqsd = parse.parse_qs(jqs)
    assert jqsd['signature']
    assert jqsd['email']
    assert jqsd['expiration']
    assert not verify_email_signature(signature=jibberish,
                                      email=jqsd['email'][0],
                                      expiration=jqsd['expiration'][0])
    # off by one
    qs = generate_unsubscribe_qs(test_email)
    qsd = parse.parse_qs(qs)
    assert qsd['signature']
    assert qsd['email']
    assert qsd['expiration']
    assert not verify_email_signature(signature=qsd['signature'][0][:-1],
                                      email=jqsd['email'][0],
                                      expiration=jqsd['expiration'][0])
    # expired
    days = 0
    expiry = datetime.utcnow() + timedelta(days=days)
    qs = generate_unsubscribe_qs(test_email, days=days)
    qsd = parse.parse_qs(qs)
    assert qsd['signature']
    assert qsd['email']
    assert qsd['expiration']
    # Should pass because signature is correct
    assert verify_email_signature(signature=qsd['signature'][0][:-1],
                                  email=jqsd['email'][0],
                                  expiration=jqsd['expiration'][0])
    assert expiry - datetime.fromtimestamp(int(qsd.get('expiration')[0])) < \
        timedelta(seconds=1)
    assert datetime.fromtimestamp(int(qsd.get('expiration')[0])) < \
        datetime.utcnow()
