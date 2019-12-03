import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def send_email(sender, recipients, subject, body_text, body_html,
               source_arn, return_arn=None, return_email=None,
               region='us-east-1'):
    # The character encoding for the email.
    charset = "UTF-8"

    # Create a new SES resource and specify a region.
    client = boto3.client('ses', region_name=region)

    if return_arn is None:
        return_arn = source_arn

    if return_email is None:
        return_email = sender

    # Try to send the email.
    try:
        # Provide the contents of the email.
        response = client.send_email(
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
    # Display an error if something goes wrong.
    except ClientError as e:
        logger.error(e.response['Error']['Message'])
        return False
    else:
        logger.info("Email sent!"),
        return response


if __name__ == '__main__':
    logger.info('Running base case test of email')
    ses_options = {
        'sender': input('Sender (you): '),
        'recipients': input('email recipients (space separated): '),
        'subject': 'Amazon SES Test (SDK for Python)',
        'body_text': 'Amazon SES Test (Python)\r\n'
                     'This email was sent with Amazon SES using the AWS SDK '
                     'for Python (Boto).',
        'body_html': '''<html>
<head></head>
<body>
  <h1>Amazon SES Test (SDK for Python)</h1>
  <p>This email was sent with
    <a href='https://aws.amazon.com/ses/'>Amazon SES</a> using the
    <a href='https://aws.amazon.com/sdk-for-python/'>
      AWS SDK for Python (Boto)</a>.</p>
</body>
</html>
            ''',
        'source_arn': input('Provide source (sender) arn: ')
    }
    resp = send_email(**ses_options)
    if resp:
        logger.info(repr(resp))
