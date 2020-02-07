import argparse
from emmaa.model import EmmaaModel


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to update a model saved on S3.')
    parser.add_argument('-m', '--model', help='Model name', required=True)
    args = parser.parse_args()

    em = EmmaaModel.load_from_s3(args.model)
    em.get_new_readings()
    em.save_to_s3()
