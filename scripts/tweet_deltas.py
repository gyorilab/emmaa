import argparse
from emmaa.analyze_tests_results import tweet_deltas


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to tweet about model and test deltas.')
    parser.add_argument('-m', '--model', help='Model name', required=True)
    parser.add_argument('-tc', '--test_corpora', nargs='+',
                        help='List of test corpora names', required=True)
    parser.add_argument('-d', '--date', help='Date in format YYYY-mm-dd',
                        required=True)
    args = parser.parse_args()

    tweet_deltas(model_name=args.model, test_corpora=args.test_corpora,
                 date=args.date)
