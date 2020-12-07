import argparse
from emmaa.model import EmmaaModel
from emmaa.model_tests import ModelManager, save_model_manager_to_s3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Script to update ModelManager stored on Amazon S3.')
    parser.add_argument('-m', '--model', help='Model name', required=True)
    args = parser.parse_args()

    model = EmmaaModel.load_from_s3(args.model)
    mm = ModelManager(model, mode='s3')
    mm.model.update_to_ndex()
    mm.save_assembled_statements()
    save_model_manager_to_s3(args.model, mm)
