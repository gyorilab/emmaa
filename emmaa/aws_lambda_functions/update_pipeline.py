"""The AWS Lambda emmaa-update-pipeline definition.

This file contains the function that starts model update cycle. It must be
placed on AWS Lambda, which can either be done manually (not recommended) or by
running:

$ python update_lambda.py update_pipeline.py emmaa-update-pipeline

in this directory.
"""

import boto3
import json


def lambda_handler(event, context):
    """Invoke individual model update functions.

    This function iterates through all models contained on S3 bucket and calls
    a different Lambda function to run model update for the models configured
    to be updated daily. It is expected that models have 'run_model_update'
    parameter in their config.json files.

    This function is designed to be placed on AWS Lambda, taking the event and
    context arguments that are passed. Note that this function must always have
    the same parameters, even if any or all of them are unused, because we do
    not have control over what Lambda sends as parameters. Parameters are
    unused in this function.

    Lambda is configured to automatically run this script every day.

    See the top of the page for the Lambda update procedure.

    Parameters
    ----------
    event : dict
        A dictionary containing metadata regarding the triggering event.
    context : object
        This is an object containing potentially useful context provided by
        Lambda. See the documentation cited above for details.

    Returns
    -------
    ret : dict
        A response returned by the latest call to emmaa-model-update function.
    """
    s3 = boto3.client('s3')
    lam = boto3.client('lambda')
    objs = s3.list_objects_v2(Bucket='emmaa', Prefix='models/', Delimiter='/')
    prefixes = objs['CommonPrefixes']
    for prefix_dict in prefixes:
        prefix = prefix_dict['Prefix']
        config_key = f'{prefix}config.json'
        obj = s3.get_object(Bucket='emmaa', Key=config_key)
        config = json.loads(obj['Body'].read().decode('utf8'))
        model_name = prefix[7:-1]
        if model_name == 'test':
            continue
        elif config.get('run_daily_update', False):
            payload = {"model": model_name}
            resp = lam.invoke(FunctionName='emmaa-model-update',
                              InvocationType='RequestResponse',
                              Payload=json.dumps(payload))
            print(resp['Payload'].read())
        else:
            payload = {"Records": [{"s3": {"object": {
                "key": f"models/{model_name}/model_2020-01-01-00-00-00.pkl"}}}]}
            resp = lam.invoke(FunctionName='emmaa-mm-update',
                              InvocationType='RequestResponse',
                              Payload=json.dumps(payload))
    return {'statusCode': 200, 'result': 'SUCCESS'}
