import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def send_email(sender, recipients, subject, body_text, body_html,
               source_arn, return_email=None, return_arn=None,
               region='us-east-1'):
    """Wrapper function for the send_email method of the boto3 SES client

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
        with <html>).
    source_arn : str
        The source ARN of the sender. Should be of the format
        "arn:aws:ses:us-east-1:123456789012:identity/user@example.com". Used
        only for sending authorization. It is the ARN of the identity that
        is associated with the sending authorization policy that permits
        the sender to send using the email address specified as the sender.
    return_email : str
        The email to which complaints and bounces are sent. Can be the same
        as the sender.
    return_arn : str
        The return path ARN for the sender. This is the ARN associated
        with the return email. Can be the same as the source_arn if return
        email is the same as the sender.
    region : str
        AWS region. Default: us-east-1

    Returns
    -------
    dict|False
        If the email was successfully sent, the response object in the form
        of a dict is returned, otherwise False is returned. The structure is:

        >>> response = {\
                'MessageId': 'EXAMPLE78603177f-7a5433e7-8edb-42ae-af10' +\
                             '-f0181f34d6ee-000000',\
                'ResponseMetadata': {\
                    '...': '...',\
                },\
            }
    """
    # The character encoding for the email.
    charset = "UTF-8"

    # Create a new SES client with the email profile
    ses = boto3.session.Session(
        profile_name='emmaa-email').client('ses', region_name=region)

    if return_arn is None:
        return_arn = source_arn

    if return_email is None:
        return_email = sender

    # Try to send the email.
    try:
        # Provide the contents of the email.
        response = ses.send_email(
            Destination={
                'ToAddresses': [rec for rec in recipients] if isinstance(
                    recipients, (list, tuple, set)) else [recipients],
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
        logger.error(e.response['Error']['Message'])
        return False
    else:
        logger.info("Email sent!"),
        return response


if __name__ == '__main__':
    logger.info('Running base case test of email')
    email_subj = input('Email subject line: ')
    msg = input('Provide a personalized message for the email body: ')
    ses_options = {
        'sender': input('Sender (you): '),
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
      AWS SDK for Python (Boto)</a>. Personal message: %s</p>'
</body>
</html>
            ''' % (email_subj, msg),
        'source_arn': input('Provide source (sender) arn: ')
    }
    resp = send_email(**ses_options)
    if resp:
        print('Email(s) sent successfully')
        print(repr(resp))
    else:
        print('Email failed to send...')
