import argparse
from emmaa.model_tests import model_to_tests


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', help='Model name', required=True)
    args = parser.parse_args()

    tests = model_to_tests(args.model, upload=True)
