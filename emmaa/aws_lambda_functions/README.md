# EMMAA AWS Infrastructure
This directory contains the definitions of AWS Lambda functions
used to orchestrate daily model updates and analysis. This document describes
how the AWS infrastructure is set up.

## AWS Lambda Functions
The process is managed by the following AWS Lambda functions:
- `emmaa-update-pipeline`
  This lambda function is triggered by a CloudWatch event rule (12 pm EST).
  This function iterates through available models in S3 bucket and checks their
  configuration files. If the model is set for daily updates, (run_daily_update
  is set to True), the `emmaa-model-update` Lambda is triggered for this model. For
  manually curated models that are tested against the literature-based models,
  the model update is skipped and the `emmaa-mm-update` Lambda function is
  triggered (even though the model manager doesn't change without model update,
  we need to rerun this step since all the time stamps for the output files are
  generated by the model manager). To specify this behavior, run_daily_update
  is set to False but run_daily_tests is True in the config file.
  If both are set to False, the model is skipped.
- `emmaa-model-update`
  This lambda function updates the given model from literature and other sources.
  It is typically triggered by the `emmaa-update-pipeline` function.
  It starts an AWS Batch job that runs `scripts/run_model_update.py` script.
  The result of this job is the updated model in the S3 bucket.
- `emmaa-mm-update`
  This lambda function runs the model assembly and updates the model
  manager. It is typically triggered when the new model is uploaded to the
  S3 bucket (though for manually curated models, it is triggered by the
  `emmaa-update-pipeline` function). It starts AWS Batch job that runs
  `scripts/update_model_manager.py` script. The result of this job is the
   updated model manager and assembled statements files on S3 and updated
   statements in the statements database.
- `emmaa-after-update`
  This lambda function is triggered when the new model manager is uploaded to
  S3 bucket. It orchestrates all other steps for the given model:
   - Starts a job to generate the model statistics for the updated model state.
   - Iterates through the test corpora specified in the model config and
     runs the testing and test statistics generation for each test corpus.
   - When both model and test statistics are generated, the model notifications
     job is triggered that tweets the model updates if the model has a Twitter
     account and sends emails to subscribed users. Note that this process
     does not send email notifications about new query results, there's a separate
     lambda function for that.
   - In parallel with the previously described steps, the job for answering
     queries is triggered.
   - If the model is used as a test corpus for other models, the tests are
     generated in parallel with previously described steps.
- `emmaa-email-notifications`
  This lambda function runs in a different cycle separately from the other lambda
  functions (6 am EST). It iterates through the emails of users who have
  registered the queries and sends emails if there are new results.

## AWS Batch
Most of the processes triggered by the lambda functions described above
(model updates, model manager updates, testing, statistics generation,
query answering, notifications) are run in AWS Batch. Each of the Batch jobs
is running a python script. The full list of scripts is in the `scripts` 
directory. To set up a Batch job it is important to configure the following:

- Job definition
  
  Here we need to set a memory limit, number of vCPUs and specify which docker
  image to use. Environment variables are also set here.
  In EMMAA we currently use three job definitions:
  - emmaa_jobdef (name is generic for historical reasons) - to run all the
  update, testing, stats jobs that have lower resource requirements.
  - emmaa_testing_jobs_def (name is misleading for historical reasons) - job
  definition with higher memory limits to run all the jobs that have higher
  resource requirements.
  - emmaa-email-notifications - to run the email notifications jobs (has
  permissions to send emails).

- Compute environment

  Here we select instance type and provisioning model (e.g. SPOT).
  In EMMAA we currently use two compute environments:
  - emmaa-models-update-test
  - emmaa-testing-jobs-env

  The names are misleading for historical reasons; the
  enviornments differ by the numbers of desired and maximum vCPUs.

- Job queue

  Job queue connects the compute environemnt to the job and can be used to
  monitor the jobs via AWS UI.
  In EMMAA we currently use two job queues:
  - emmaa-models-update-test - for faster jobs with lower resource requirements.
  - emmaa-after-update - for slower jobs with higher resource requirements.

  The names are misleading for historical reasons.

- Command to run

  Batch job is run by a command and in EMMAA the commands are created in
  lambda functions.

Job definitions and queues are selected by the lambda function that triggers
the job depending on the model's resource requirements.

## AWS Simple Storage Service (S3)

All versions of model states and other outputs are stored on S3. The bucket
has the following directories:

- `models` - model states (pickle) and model coniguration files (JSON).
- `results` - assembled model manager objects (pickle) and test results (JSON).
- `assembled` - assembled statements (gzip JSON and JSONL).
- `model_stats` - model statistics (JSON).
- `stats` - test statistics (JSON).
- `tests` - test corpora (pickle).
- `exports` - different exports of model state (BNGL, SBML, TSV, KAPPA, GROMET, etc.).
- `paths` - graph paths extracted from test results (JSONL).
- `papers` - IDs of papers used to build a model (JSON).
- `query_images` - plots of simulated query results (PNG).

All of the above directories internally have subdirectories for each model.
All files are versioned with the timestamp created during the model manager assembly.