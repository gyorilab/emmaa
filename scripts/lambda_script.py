"""The AWS Lambda update definition.

This file contains the function that will be run when Lambda is triggered. It
must be placed on s3, which can either be done manually (not recommended) or
by running:

$ python update_lambda.py

in this directory.
"""

import json
import boto3
from io import StringIO, BytesIO
from datetime import datetime

def lambda_handler(event, context):
    """Initial batch jobs for any changed models or tests.

    This function is designed to be placed on lambda, taking the event and
    context arguments that are passed, and extracting the names of the
    uploaded (which includes changed) model or test definitions on s3.
    Lambda is configured to be triggered by any such changes, and will
    automatically run this script.

    See the top of the page for the Lambda update procedure.

    Note that this function must always have the same parameters, even if any
    or all of them are unused, because we do not have control over what Lambda
    sends as parameters. For more information on the context parameter, see
    here:

      https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    And for more informationn about AWS Lambda handlers, see here:

      https://docs.aws.amazon.com/lambda/latest/dg/python-programming-model-handler-types.html


    Parameters
    ----------
    event : dict
        A dictionary containing metadata regarding the triggering event. In
        this case, we are expecting 'Records', each of which contains a record
        of a file that was added (or changed) on s3.
    context : object
        This is an object containing potentially useful context provided by
        Lambda. See the documentation cited above for details.

    Returns
    -------
    ret : dict
        A dict containing 'statusCode', with a valid HTTP status code, and any
        other data to be returned to Lambda.
    """
    s3 = boto3.client('s3')
    batch = boto3.client('batch')
    records = event['Records']
    for rec in records:
        try:
            model_key = rec['s3']['object']['key']
        except KeyError:
            pass
        model_name = model_key.split('/')[1]
        data = [{"name": "test1", "passed": True}]
        data_str = json.dumps(data)
        print(data_str)
        dt_str = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
        f = BytesIO(data_str.encode('utf-8'))
        s3.upload_fileobj(f, 'emmaa', f'results/{model_name}/{dt_str}.json')

    return {'statusCode': 200, 'body': "DONE!"}
 
