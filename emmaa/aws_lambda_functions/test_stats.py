"""The AWS Lambda emmaa-test-stats definition.

This file contains the function that will be run when Lambda is triggered. It
must be placed on s3, which can either be done manually (not recommended) or
by running:

$ python update_lambda.py test_stats.py emmaa-test-stats

in this directory.
"""

import boto3
from datetime import datetime

JOB_DEF = 'emmaa_jobdef'
QUEUE = 'emmaa-models-update-test'
PROJECT = 'aske'
PURPOSE = 'update-emmaa-test-stats'
BRANCH = 'origin/master'


def lambda_handler(event, context):
    """Create a batch job to generate model statistics.

    This function is designed to be placed on lambda, taking the event and
    context arguments that are passed, and extracting the names of the
    uploaded (which includes changed) model or test definitions on s3.
    Lambda is configured to be triggered by any such changes, and will
    automatically run this script.

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
    batch = boto3.client('batch')
    records = event['Records']
    for rec in records:
        try:
            model_key = rec['s3']['object']['key']
        except KeyError:
            pass
        model_name = model_key.split('/')[1]
        test_corpus = model_key.split('/')[-1][8:-25]
        if not test_corpus:
            test_corpus = 'large_corpus_tests'
        core_command = 'bash scripts/git_and_run.sh'
        if BRANCH is not None:
            core_command += f' --branch {BRANCH}'
        core_command += (' python scripts/run_model_stats_from_s3.py'
                         f' --model {model_name} --stats_mode tests'
                         f' --tests {test_corpus}')
        print(core_command)
        cont_overrides = {
            'command': ['python', '-m', 'indra.util.aws', 'run_in_batch',
                        '--project', PROJECT, '--purpose', PURPOSE,
                        core_command]
            }
        now_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        ret = batch.submit_job(
            jobName=f'{model_name}_{test_corpus}_stats_{now_str}',
            jobQueue=QUEUE, jobDefinition=JOB_DEF,
            containerOverrides=cont_overrides)
        job_id = ret['jobId']

    return {'statusCode': 200, 'result': 'SUCCESS', 'job_id': job_id}
