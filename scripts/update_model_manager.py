import argparse
from emmaa.model_tests import update_model_manager_on_s3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Script to update ModelManager stored on Amazon S3.')
    parser.add_argument('-m', '--model', help='Model name', required=True)
    args = parser.parse_args()

    mm.model.update_to_ndex()
    mm.save_assembled_statements()
    mm = update_model_manager_on_s3(args.model)
