import argparse
from emmaa.model_tests import run_model_tests_from_s3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Script to run tests against models, both stored on '
                        'Amazon S3.')
    parser.add_argument('-m', '--model', help='Model name', required=True)
    parser.add_argument('-t', '--test', required=True,
                        help='Test file name (optional). If not specified, '
                             'runs all available tests against the model.')
    args = parser.parse_args()

    run_model_tests_from_s3(args.model, args.test, upload_results=True)

