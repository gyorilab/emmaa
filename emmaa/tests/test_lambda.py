import boto3
import pickle
import unittest
from indra_reading.batch.monitor import BatchMonitor

from emmaa.aws_lambda_functions.model_tests import lambda_handler, QUEUE
from emmaa.util import make_date_str, get_s3_client

RUN_STATI = ['SUBMITTED', 'PENDING', 'RUNNABLE', 'RUNNING']
DONE_STATI = ['SUCCEEDED', 'FAILED']


def __get_jobs(batch):
    job_ids = {}
    for status in RUN_STATI + DONE_STATI:
        resp = batch.list_jobs(jobQueue=QUEUE, jobStatus=status)
        if 'jobSummaryList' in resp.keys():
            job_ids[status] = [s['jobId'] for s in resp['jobSummaryList']]
    return job_ids


@unittest.skip('Local test without starting up batch job not yet implemented')
def test_handler():
    """Test the lambda handler locally."""
    dts = make_date_str()
    key = f'models/test/test_model_{dts}.pkl'
    event = {'Records': [{'s3': {'object': {'key': key}}}]}
    context = None
    res = lambda_handler(event, context)
    print(res)
    assert res['statusCode'] == 200, res
    assert res['result'] == 'SUCCESS', res
    assert res['job_id'], res
    job_id = res['job_id']

    results = {}
    monitor = BatchMonitor(QUEUE, [{'jobId': job_id}])
    monitor.watch_and_wait(result_record=results)
    print(results)
    assert job_id in [job_def['jobId'] for job_def in results['succeeded']], \
        results['failed']

    s3 = get_s3_client()
    s3_res = s3.list_objects(Bucket='emmaa', Prefix='results/test/' + dts[:10])
    print(s3_res.keys())
    assert s3_res, s3_res


@unittest.skip('Unfinished test. See comments in code')
def test_s3_response():
    """Change a file on s3 and check for the correct response."""
    # This will be a white-box test. We will check progress at various stages.
    s3 = get_s3_client()
    batch = boto3.client('batch')

    # Define some fairly random parameters.
    key = f'models/test/model_{make_date_str()}.pkl'
    data = {'test_message': 'Hello world!'}

    # This should trigger the lambda to start a batch job.
    s3.put_object(Bucket='emmaa', Key=key, Body=pickle.dumps(data))

    # TODO
    #  1. verify that lambda has started a batch job
    #  2. kill batch job
    #  3. delete uploaded pickle
