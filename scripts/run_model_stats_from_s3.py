import argparse
from emmaa.analyze_tests_results import generate_model_stats_on_s3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Script to generate statistic for the latest round of'
                        'tests and save to Amazon S3.')
    parser.add_argument('-m', '--model', help='Model name', required=True)
    parser.add_argument('-t', '--tests', required=True,
                        help='Test file name (optional). Default is '
                        'large_corpus_tests')
    args = parser.parse_args()

    generate_model_stats_on_s3(args.model, args.tests, upload_stats=True)
