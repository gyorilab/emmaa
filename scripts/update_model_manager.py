import argparse
from emmaa.model_tests import update_model_manager_on_s3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Script to update ModelManager stored on Amazon S3.')
    parser.add_argument('-m', '--model', help='Model name', required=True)
    args = parser.parse_args()

    update_model_manager_on_s3(args.model)
