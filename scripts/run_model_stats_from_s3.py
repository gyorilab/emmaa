import argparse
from emmaa.analyze_tests_results import generate_model_stats_on_s3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Script to generate statistic for the latest round of'
                        'tests and save to Amazon S3.')
    parser.add_argument('-m', '--model', help='Model name', required=True)
    args = parser.parse_args()

    generate_model_stats_on_s3(args.model, upload_stats=True)
