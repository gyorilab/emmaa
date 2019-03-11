import json
import logging
from collections import defaultdict
from util import find_latest_s3_files, load_test_results_from_s3
from indra.statements.statements import Statement


class TestRound():
    def __init__(self, key):
        self.key = key
        self.test_results = load_test_results_from_s3(key)

    def has_path(self, result):
        return result['result_json']['path_found']

    def get_total_tests(self):
        return len(self.test_results)-1

    def get_number_passed_tests(self):
        path_count = 0
        for result in self.test_results[1:]:
            if self.has_path(result):
                path_count += 1
        return path_count

    def passed_over_total(self):
        return self.get_number_passed_tests()/self.get_total_tests()

    def get_number_statements(self):
        return self.test_results[0]['number_of_statements']

    def get_statements(self):
        return self.test_results[0]['statements']

    def get_passed_tests(self):
        # change to english!
        passed_tests = []
        for result in self.test_results[1:]:
            if self.has_path(result):
                passed_tests.append(Statement._from_json(res['test_json']))
        return passed_tests

    def get_path_descriptions(self):
        path_descriptions = []
        for res in self.test_results[1:]:
            if res['result_json']['path_found']:
                path_descriptions.append(res['english_result'])

    def find_numeric_delta(self, other_round, one_round_numeric_func):
        return self.one_round_func() - other_round.one_round_numeric_func()

    def find_content_delta(self, other_round, one_round_content_func):
        changed_items = {'added': [], 'removed': []}
        for item in self.one_round_content_func():
            if item not in other_round.one_round_content_func():
                changed_items['added'].append(item)
        for item in other_round.one_round_content_func():
            if item not in self.one_round_content_func():
                changed_items['removed'].append(item)
        return changed_items


def run_for_multiple_rounds(number_of_tests, model_name, one_round_func):
    keys = find_latest_s3_files(
           number_of_tests, 'emmaa',
           f'results/{model_name}results_', extension='.json')
    data = []
    for key in keys:
        tr = TestRound(key)
        current_data = tr.one_round_func()
        data.append(current_data)
    return data

# def find_delta()