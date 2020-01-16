import argparse
from emmaa.answer_queries import answer_queries_from_s3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Script to answer queries registered for a model'
                        ' using a ModelManager saved on S3')
    parser.add_argument('-m', '--model', help='Model name', required=True)
    args = parser.parse_args()

    answer_queries_from_s3(args.model, db=None)
