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

    This function is designed to be placed on AWS Lambda, taking the event and
    context arguments that are passed. Note that this function must always have
    the same parameters, even if any or all of them are unused, because we do
    not have control over what Lambda sends as parameters. Event parameter is
    used here to pass which model was updated.

    This function will look up config file for a given model, check which
    test corpora should be used to test this model and invoke individual
    functions for each test coprus.

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
        A response returned by the latest call to emmaa-model-test function.
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
        config_key = f'models/{model_name}/config.json'
        config = s3.get_object(Bucket='emmaa', Key=config_key)
        tests = config['test'].get('test_corpus', 'large_corpus_tests.pkl')
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
