import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

email_profile = 'indralabs-email'
email_bucket = 'emmaa-notifications'
notifications_sender_default = 'emmaa_notifications@indra.bio'
notifications_return_default = 'feedback@indra.bio'
indra_bio_ARN_id = os.environ.get('INDRA_BIO_ARN')


def _get_ses_client(region='us-east-1'):
    # First look for keys in environ:
    ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY_ID')
    SECRET_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    if ACCESS_KEY and SECRET_KEY:
        logger.info('Using access keys from environment variables to get '
                    'ses client.')
        ses = boto3.session.Session(
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY).client(
            'ses', region_name=region)
    # If not, try to get the email_profile from the AWS credentials file
    else:
        ses = boto3.session.Session(
            profile_name=email_profile).client(
            'ses', region_name=region)
        logger.info('Using AWS credentials file to get ses client.')
    return ses


def send_email(sender, recipients, subject, body_text, body_html,
               source_arn=indra_bio_ARN_id, return_email=None,
               return_arn=None, region='us-east-1'):
    """Wrapper function for the send_email method of the boto3 SES client

    IMPORTANT: sending is limited to 14 emails per second.

    See more at:
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference +
    /services/ses.html#SES.Client.send_email
    https://docs.aws.amazon.com/ses/latest/APIReference/API_SendEmail.html
    and python example at
    https://docs.aws.amazon.com/ses/latest/DeveloperGuide/ +
    sending-authorization-delegate-sender-tasks-email.html


    Parameters
    ----------
    sender : str
        A valid email address to use in the Source field
    recipients : iterable[str] or str
        A valid email address or a list of valid email addresses. This will
        fill out the Recipients field.
    subject : str
        The email subject
    body_text : str
        The text body of the email
    body_html : str
        The html body of the email. Must be a valid html body (starting
        with <html>, ending with </html>).
    source_arn : str
        The source ARN of the sender. Should be of the format
        "arn:aws:ses:us-east-1:123456789012:identity/user@example.com" or
        "arn:aws:ses:us-east-1:123456789012:identity/example.com".
        Used only for sending authorization. It is the ARN of the identity
        that is associated with the sending authorization policy that
        permits the sender to send using the email address specified as the
        sender. Example: the owner of the domain "example.com" can send an
        email from any address using @example.com, as long as the associated
        source_arn is
        "arn:aws:ses:us-east-1:123456789012:identity/example.com"
    return_email : str
        The email to which complaints and bounces are sent. Can be the same
        as the sender.
    return_arn : str
        The return path ARN for the sender. This is the ARN associated
        with the return email. Can be the same as the source_arn if return
        email is the same as the sender.
    region : str
        AWS region to use for the SES client. Default: us-east-1

    Returns
    -------
    dict
        The API response object in the form of a dict is returned. The
        structure is:

        >>> response = {\
                'MessageId': 'EXAMPLE78603177f-7a5433e7-8edb-42ae-af10' +\
                             '-f0181f34d6ee-000000',\
                'ResponseMetadata': {\
                    '...': '...',\
                },\
            }
    """
    # Check if there is any source ARN
    if not source_arn:
        source_arn = os.environ.get('INDRA_BIO_ARN')
        if source_arn is None:
            logger.error('No SourceArn found, please set it using '
                         'the environment variable INDRA_BIO_ARN or '
                         'provided source_arn in arguments.')
            raise ValueError('source_arn must be provided or specified in '
                             'environment.')
        logger.info('Found SourceArn in os environment variable'
                    'INDRA_BIO_ARN')

    # The character encoding for the email.
    charset = "UTF-8"

    # Create a new SES client with the email profile
    ses = _get_ses_client(region)

    if return_arn is None:
        return_arn = source_arn

    if return_email is None:
        return_email = sender

    to_addresses = [rec for rec in recipients] if isinstance(
        recipients, (list, tuple, set)) else [recipients]

    # Try to send the email.
    try:
        # Provide the contents of the email.
        response = ses.send_email(
            Destination={
                'ToAddresses': to_addresses,
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': charset,
                        'Data': body_html,
                    },
                    'Text': {
                        'Charset': charset,
                        'Data': body_text,
                    },
                },
                'Subject': {
                    'Charset': charset,
                    'Data': subject,
                },
            },
            Source=sender,
            ReturnPath=return_email,
            SourceArn=source_arn,
            ReturnPathArn=return_arn
        )
    # Log error if something goes wrong.
    except ClientError as e:
        logger.error(f'Failed to send email to {", ".join(to_addresses)}')
        logger.error(e.response['Error']['Message'])
        response = e.response
    else:
        logger.info(f'Email sent to {", ".join(to_addresses)} successfully'),
    return response


def _get_max_24h_send(ses_client):
    res = ses_client.get_send_quota()
    return int(res['Max24HourSend'])


def _get_sent_last_24h(ses_client):
    res = ses_client.get_send_quota()
    return int(res['SentLast24Hours'])


def _get_quota_sent_max_ratio(ses_client):
    res = ses_client.get_send_quota()
    return res['SentLast24Hours']/res['Max24HourSend']


def close_to_quota_max(used_quota=0.95, region='us-east-1'):
    """Check if the send quota is close to be exceeded

    If the total quota for the 24h cycle is Q, the currently used quota is q
    and 'used_quota' is r, return True if q/Q > r, otherwise return False.

    Parameters
    ----------
    used_quota : float
        A float between 0 and 1.0. This number specifies the fraction of
        send quota currently used. Default: 0.95
    region : str
        A valid AWS region. The region to check the quota in.
        Default: us-east-1.

    Returns
    -------
    bool
        True if the quota is close to be exceeded with respect to the
        provided ratio 'used'.
    """
    ses = boto3.session.Session(
        profile_name=email_profile).client('ses', region_name=region)
    ratio_used = _get_quota_sent_max_ratio(ses)
    return ratio_used > used_quota


def get_send_statistics(region='us-east-1'):
    """Return the sending statistics, like bounce and complaint rates

    See
    https://boto3.amazonaws.com/v1/documentation/api/latest/
    reference/services/ses.html#SES.Client.get_send_statistics
    for more info

    Parameters
    ----------
    region : Optional[str]
        Specify AWS region

    Returns
    -------
    dict
        Response syntax:
            {
                'SendDataPoints': [
                    {
                        'Timestamp': datetime(2015, 1, 1),
                        'DeliveryAttempts': 123,
                        'Bounces': 123,
                        'Complaints': 123,
                        'Rejects': 123
                    },
                ]
            }
    """
    ses = _get_ses_client(region)
    return ses.get_send_statistics()


if __name__ == '__main__':
    logger.info('Running base case test of email')
    email_subj = input('Email subject line: ')
    msg = input('Provide a personalized message for the email body: ')
    ses_options = {
        'sender': notifications_sender_default,
        'recipients': input('email recipients (space separated): ').split(),
        'subject': email_subj,
        'body_text': f'{email_subj}\r\n'
                     'This email was sent with Amazon SES using the AWS SDK '
                     'for Python (Boto). Personal message: %s' % msg,
        'body_html': '''<html>
<head></head>
<body>
  <h1>%s</h1>
  <p>This email was sent with
    <a href='https://aws.amazon.com/ses/'>Amazon SES</a> using the
    <a href='https://aws.amazon.com/sdk-for-python/'>
      AWS SDK for Python (Boto)</a>. Personal message: %s</p>
</body>
</html>''' % (email_subj, msg),
        'source_arn': input('Provide source (sender) arn: '),
        'return_email': input('Specify ReturnPath: '),
        'return_arn': input('Specify ReturnPathArn: ')
    }
    resp = send_email(**ses_options)
    print(repr(resp))
