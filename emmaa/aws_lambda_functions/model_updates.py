"""The AWS Lambda emmaa-model-update definition.

This file contains the function that starts model update cycle. It must be
placed on AWS Lambda, which can either be done manually (not recommended) or by
running:

$ python update_lambda.py model_updates.py emmaa-model-update

in this directory.
"""

import boto3
from datetime import datetime

JOB_DEF = 'emmaa_jobdef'
QUEUE = 'emmaa-models-update-test'
PROJECT = 'aske'
PURPOSE = 'update-emmaa-models'
BRANCH = 'origin/master'


def lambda_handler(event, context):
    """Create a batch job to update models on s3 and NDEx.

    This function is designed to be placed on AWS Lambda, taking the event and
    context arguments that are passed. Note that this function must always have
    the same parameters, even if any or all of them are unused, because we do
    not have control over what Lambda sends as parameters. Event parameter is
    used to pass model_name argument.

    This Lambda function is configured to be invoked by emmaa-update-pipeline
    Lambda function.

    See the top of the page for the Lambda update procedure.

    Parameters
    ----------
    event : dict
        A dictionary containing metadata regarding the triggering event. In
        this case the dictionary contains model name.
    context : object
        This is an object containing potentially useful context provided by
        Lambda. See the documentation cited above for details.

    Returns
    -------
    ret : dict
        A dict containing 'statusCode', with a valid HTTP status code, 'result',
        and 'job_id' to be returned to Lambda.
    """
    model_name = event['model']
    batch = boto3.client('batch')
    core_command = 'bash scripts/git_and_run.sh'
    if BRANCH is not None:
        core_command += f' --branch {BRANCH} '
    core_command += (f'python scripts/run_model_update.py --model {model_name}')
    print(core_command)
    cont_overrides = {
        'command': ['python', '-m', 'indra.util.aws', 'run_in_batch',
                    '--project', PROJECT, '--purpose', PURPOSE,
                    core_command]
        }
    now_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    ret = batch.submit_job(jobName=f'{model_name}_update_{now_str}',
                           jobQueue=QUEUE, jobDefinition=JOB_DEF,
                           containerOverrides=cont_overrides)
    job_id = ret['jobId']

    return {'statusCode': 200, 'result': 'SUCCESS', 'job_id': job_id}
