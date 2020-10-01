"""The AWS Lambda emmaa-after-update definition.

This file contains the function that will be run when Lambda is triggered. It
must be placed on s3, which can either be done manually (not recommended) or
by running:

$ python update_lambda.py after_update.py emmaa-after-update

in this directory.
"""

import boto3
import json
from datetime import datetime


batch = boto3.client('batch')
JOB_DEF = 'emmaa_jobdef'
QUEUE = 'emmaa-models-update-test'
PROJECT = 'aske'
BRANCH = 'origin/master'
now_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
date = datetime.utcnow().strftime('%Y-%m-%d')


def submit_batch_job(script_command, purpose, job_name, wait_for=None):
    print(f'Submitting job {job_name}')
    core_command = 'bash scripts/git_and_run.sh'
    if BRANCH is not None:
        core_command += f' --branch {BRANCH}'
    core_command += script_command
    print(core_command)
    cont_overrides = {
        'command': ['python', '-m', 'indra.util.aws', 'run_in_batch',
                    '--project', PROJECT, '--purpose', purpose,
                    core_command]
        }
    kwargs = {}
    if wait_for:
        kwargs['dependsOn'] = [{'jobId': job_id, 'type': 'SEQUENTIAL'}
                               for job_id in wait_for]
    ret = batch.submit_job(
        jobName=job_name,
        jobQueue=QUEUE, jobDefinition=JOB_DEF,
        containerOverrides=cont_overrides, **kwargs)
    job_id = ret['jobId']
    print(f"Result from job submission: {job_id}")
    return job_id


def lambda_handler(event, context):
    """Submit model tests, model and test stats, and query batch jobs.

    This function is designed to be placed on AWS Lambda, taking the event and
    context arguments that are passed. Note that this function must always have
    the same parameters, even if any or all of them are unused, because we do
    not have control over what Lambda sends as parameters. Event parameter is
    used here to pass which model manager was updated.

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
        A dict containing 'statusCode', with a valid HTTP status code, and any
        other data to be returned to Lambda.
    """
    s3 = boto3.client('s3')
    records = event['Records']
    for rec in records:
        try:
            model_key = rec['s3']['object']['key']
        except KeyError:
            pass
        model_name = model_key.split('/')[1]

        # Store all stats jobs IDs
        stats_job_ids = []

        # Submit model stats job
        model_stats_command = (' python scripts/run_model_stats_from_s3.py'
                               f' --model {model_name}  --stats_mode model')
        model_stats_id = submit_batch_job(
            model_stats_command, 'update-emmaa-model-stats',
            f'{model_name}_model_stats_{now_str}')
        stats_job_ids.append(model_stats_id)

        # Find all test corpora for daily runi
        config_key = f'models/{model_name}/config.json'
        obj = s3.get_object(Bucket='emmaa', Key=config_key)
        config = json.loads(obj['Body'].read().decode('utf8'))
        tests = config['test'].get('test_corpus', 'large_corpus_tests')
        if isinstance(tests, str):
            tests = [tests]

        # For each test run the test and test stats
        for test_corpus in tests:
            test_command = (' python scripts/run_model_tests_from_s3.py'
                            f' --model {model_name} --tests {test_corpus}')
            test_id = submit_batch_job(
                test_command, 'update-emmaa-results',
                f'{model_name}_{test_corpus}_tests_{now_str}')
            test_stats_command = (' python scripts/run_model_stats_from_s3.py'
                                  f' --model {model_name} --stats_mode tests'
                                  f' --tests {test_corpus}')
            test_stats_id = submit_batch_job(
                test_stats_command, 'update-emmaa-test-stats',
                f'{model_name}_{test_corpus}_stats_{now_str}', [test_id])
            stats_job_ids.append(test_stats_id)

        # Submit twitter job
        if config.get('twitter'):
            twitter_command = (
                f' python scripts/tweet_deltas.py --model {model_name} '
                f'--test_corpora {" ".join(tc for tc in tests)} --date {date}')
            submit_batch_job(twitter_command, 'update-twitter-status',
                             f'{model_name}_twitter_{now_str}', stats_job_ids)
        # Run queries
        query_command = (' python scripts/answer_queries_from_s3.py'
                         f' --model {model_name}')
        submit_batch_job(query_command, 'update-emmaa-queries',
                         f'{model_name}_queries_{now_str}')

        # Make tests if configured
        if config.get('make_tests', False):
            test_update_command = (' python scripts/model_to_tests.py'
                                   f' --model {model_name}')
            submit_batch_job(test_update_command, 'update-emmaa-tests',
                             f'{model_name}_test_update_{now_str}')

    return 'All jobs sumbitted'
