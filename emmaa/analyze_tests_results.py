import json
import logging
from collections import defaultdict
from util import get_s3_client, find_latest_s3_files
# load test results from s3
# find number of passed tests in one test
# find passed tests for n tests


def load_test_results_from_s3(key):
    client = get_s3_client()
    logger.info(f'Loading test results from {key}')
    obj = client.get_object(Bucket='emmaa', Key=key)
    test_results = json.loads(obj['Body'].read().decode('utf8'))
    return test_results


class TestRound():
    def __init__(key):
        self.key = key
        self.test_results = load_test_results_from_s3(key)

    def get_total_tests(self):
        return len(self.test_results)

    def get_number_passed_tests(self):
        path_count = 0
        for res in self.test_results:
                if res['result_json']['path_found']:
                    path_count += 1
        return path_count

    def passed_over_total(self):
        return self.get_passed_tests()/self.get_passed_tests()


def run_for_multiple_rounds(number_of_tests, model_name, get_data):
    # get_data - some function that gets some data for one test round
    keys = find_latest_s3_files(
           number_of_tests, 'emmaa',
           f'results/{model_name}results_', extension='.json')
    data = []
    for key in keys:
        test_results = load_test_results_from_s3(key)
        current_data = get_data(test_results)
        data.append(current_data)
    return data


# def find_delta(current_results, previous_results):
    