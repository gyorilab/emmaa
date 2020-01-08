import argparse
from emmaa.analyze_tests_results import generate_stats_on_s3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Script to generate statistic for the latest round of'
                        'tests and save to Amazon S3.')
    parser.add_argument('-m', '--model', help='Model name', required=True)
    parser.add_argument('-s', '--stats_mode', help='Mode of stats (model or'
                        ' tests)', required=True)
    parser.add_argument('-t', '--tests', default='large_corpus_tests',
                        help='Test file name.',)
    args = parser.parse_args()

    generate_stats_on_s3(model_name=args.model, mode=args.stats_mode,
                         test_corpus_str=args.tests, upload_stats=True)
