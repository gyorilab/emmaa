"""The AWS Lambda email-notification definition

This file contains the function that will be run when Lambda is triggered. It
must be placed on s3, which can either be done manually (not recommended) or
by running:

$ python update_lambda.py email_notifications.py emmaa-email-notifications

in this directory.
"""

import boto3
import json


def lambda_handler(event, context):
    """Invoke batch job that checks for query deltas per subscribed user

    """
    pass
