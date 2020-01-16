"""The AWS Lambda emmaa-test-pipeline definition.

This file contains the function that will be run when Lambda is triggered. It
must be placed on s3, which can either be done manually (not recommended) or
by running:

$ python update_lambda.py test_pipeline.py emmaa-test-pipeline

in this directory.
"""

import boto3
import json


def lambda_handler(event, context):
    """Invoke individual test corpus functions.

    This function is designed to be placed on lambda, taking the event and
    context arguments that are passed. Event parameter is used here to pass
    name of the model.

    This Lambda function is configured to be invoked by emmaa-after-update
    Lambda function.

    Parameters
    ----------
    event : dict
        A dictionary containing metadata regarding the triggering event. In
        this case the dictionary contains 'model' key.
    context : object
        This is an object containing potentially useful context provided by
        Lambda. See the documentation cited above for details.

    Returns
    -------
    ret : dict
        A response returned by the latest call to emmaa-model-test function.
    """
    s3 = boto3.client('s3')
    lam = boto3.client('lambda')
    model_name = event['model']
    config_key = f'models/{model_name}/config.json'
    obj = s3.get_object(Bucket='emmaa', Key=config_key)
    config = json.loads(obj['Body'].read().decode('utf8'))
    tests = config['test'].get('test_corpus', 'large_corpus_tests')
    if isinstance(tests, str):
        resp = lam.invoke(FunctionName='emmaa-model-test',
                          InvocationType='RequestResponse',
                          Payload=json.dumps({"model": model_name,
                                              "tests": tests}))
    elif isinstance(tests, list):
        for test in tests:
            resp = lam.invoke(FunctionName='emmaa-model-test',
                              InvocationType='RequestResponse',
                              Payload=json.dumps({"model": model_name,
                                                  "tests": test}))
    print(resp['Payload'].read())
    return {'statusCode': 200, 'result': 'SUCCESS'}
