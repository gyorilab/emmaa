"""The AWS Lambda emmaa-mm-update definition.

This file contains the function that updates model manager object in S3. It
must be placed on AWS Lambda, which can either be done manually (not
recommended) or by running:

$ python update_lambda.py model_manager_update.py emmaa-mm-update

in this directory.
"""

import boto3
from datetime import datetime

JOB_DEF = 'emmaa_jobdef'
QUEUE = 'emmaa-models-update-test'
PROJECT = 'aske'
PURPOSE = 'update-emmaa-model-manager'
BRANCH = 'origin/master'


def lambda_handler(event, context):
    """Create a batch job to update model manager on s3.

    This function is designed to be placed on AWS Lambda, taking the event and
    context arguments that are passed. Note that this function must always have
    the same parameters, even if any or all of them are unused, because we do
    not have control over what Lambda sends as parameters. This Lambda
    function is configured to be triggered when the model is updated on S3.

    See the top of the page for the Lambda update procedure.

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
        A dict containing 'statusCode', with a valid HTTP status code, 'result',
        and 'job_id' to be returned to Lambda.
    """
    batch = boto3.client('batch')
    records = event['Records']
    for rec in records:
        try:
            model_key = rec['s3']['object']['key']
        except KeyError:
            pass
        model_name = model_key.split('/')[1]
        core_command = 'bash scripts/git_and_run.sh'
        if BRANCH is not None:
            core_command += f' --branch {BRANCH}'
        core_command += (' python scripts/update_model_manager.py'
                         f' --model {model_name}')
        cont_overrides = {
            'command': ['python', '-m', 'indra.util.aws', 'run_in_batch',
                        '--project', PROJECT, '--purpose', PURPOSE,
                        core_command]
            }
        now_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        ret = batch.submit_job(jobName=f'{model_name}_mm_update_{now_str}',
                               jobQueue=QUEUE, jobDefinition=JOB_DEF,
                               containerOverrides=cont_overrides)
        job_id = ret['jobId']

    return {'statusCode': 200, 'result': 'SUCCESS', 'job_id': job_id}
