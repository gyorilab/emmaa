"""The AWS Lambda update definition.

This file contains the function that will be run when Lambda is triggered. It
must be placed on s3, which can either be done manually (not recommended) or
by running:

$ python update_lambda.py

in this directory.
"""

import boto3

# Note that all non-standard imports will need to be added to the update script
# including secondary, tertiary, and so forth imports.
from emmaa.util import make_date_str

JOB_DEF = 'emmaa_jobdef'
QUEUE = 'run_db_lite_queue'
PROJECT = 'aske'
PURPOSE = 'update-emmaa-results'
BRANCH = 'indralab/master'


def lambda_handler(event, context):
    """Initial batch jobs for any changed models or tests.

    This function is designed to be placed on lambda, taking the event and
    context arguments that are passed, and extracting the names of the
    uploaded (which includes changed) model or test definitions on s3.
    Lambda is configured to be triggered by any such changes, and will
    automatically run this script.

    See the top of the page for the Lambda update procedure.

    Note that this function must always have the same parameters, even if any
    or all of them are unused, because we do not have control over what Lambda
    sends as parameters. For more information on the context parameter, see
    here:

      https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    And for more informationn about AWS Lambda handlers, see here:

      https://docs.aws.amazon.com/lambda/latest/dg/python-programming-model-handler-types.html


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
        core_command = ('bash emmaa/scripts/update_git_and_run.sh'
                        f' {BRANCH} '
                        '"\'[{{\\"name\\": \\"test\\", \\"passed\\": true}}]\''
                        f' > {fn};'
                        f' aws s3 cp {fn}'
                        f' results/{model_name}/{fn}"')
        print(core_command)
        cont_overrides = {
            'command': ['python', '-m', 'indra.util.aws', 'run_in_batch',
                        '--project', PROJECT, '--purpose', PURPOSE,
                        core_command]
            }
        ret = batch.submit_job(jobName=f'{model_name}_{make_date_str()}',
                               jobQueue=QUEUE, jobDefinition=JOB_DEF,
                               containerOverrides=cont_overrides)
        job_id = ret['jobId']

    return {'statusCode': 200, 'result': 'SUCCESS', 'job_id': job_id}
