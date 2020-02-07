"""The AWS Lambda emmaa-after-update definition.

This file contains the function that will be run when Lambda is triggered. It
must be placed on s3, which can either be done manually (not recommended) or
by running:

$ python update_lambda.py after_update.py emmaa-after-update

in this directory.
"""

import boto3
import json


def lambda_handler(event, context):
    """Invoke model stats, test pipeline and query functions.

    This function is designed to be placed on AWS Lambda, taking the event and
    context arguments that are passed. Note that this function must always have
    the same parameters, even if any or all of them are unused, because we do
    not have control over what Lambda sends as parameters. Event parameter is
    used here to pass which model manager was updated.

    Lambda is configured to run this script when ModelManager object is
    updated.

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
    lam = boto3.client('lambda')
    records = event['Records']
    for rec in records:
        try:
            model_key = rec['s3']['object']['key']
        except KeyError:
            pass
        model_name = model_key.split('/')[1]
        payload = {"model": model_name}
        for func in ['emmaa-model-stats', 'emmaa-test-pipeline',
                     'emmaa-queries']:
            resp = lam.invoke(FunctionName=func,
                              InvocationType='RequestResponse',
                              Payload=json.dumps(payload))
            print(resp['Payload'].read())
        config_key = f'models/{model_name}/config.json'
        obj = s3.get_object(Bucket='emmaa', Key=config_key)
        config = json.loads(obj['Body'].read().decode('utf8'))
        if config.get('make_tests', False):
            resp = lam.invoke(FunctionName='emmaa-test-update',
                              InvocationType='RequestResponse',
                              Payload=json.dumps(payload))
            print(resp['Payload'].read())
    return {'statusCode': 200, 'result': 'SUCCESS'}
