import boto3
import pickle
from datetime import datetime


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
