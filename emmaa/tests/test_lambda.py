import boto3
import pickle
from datetime import datetime

from lambda_script import lambda_handler


def now_str():
    return datetime.utcnow().strftime('%Y-%m-%h-%H-%M-%S')


def test_handler():
    """Test the lambda handler locally."""
    dts = now_str()
    event = {'Records': [
        {'s3': {'object': {'key': f'models/test/test_model_{dts}.pkl'}}}
        ]}
    context = None
    res = lambda_handler(event, context)
    print(res)
    assert res['statusCode'] == 200, res
    assert res['body'].startswith('Submitted'), res
    s3 = boto3.client('s3')
    s3_res = s3.list_objects(Bucket='emmaa', Prefix='results/test/' + dts[:10])
    print(s3_res)
    assert s3_res, s3_res


def test_s3_response():
    """Change a file on s3 and check for the correct response."""
    # This will be a white-box test. We will check progress at various stages.
    s3 = boto3.client('s3')
    batch = boto3.client('batch')

    # Define some fairly random parameters.
    key = f'models/test/model_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}.pkl'
    data = {'test_message': 'Hello world!'}

    # This should trigger the lambda to start a batch job.
    s3.put_object(Bucket='emmaa', Key=key, Body=pickle.dumps(data))
