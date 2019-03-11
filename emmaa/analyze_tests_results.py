import json
import logging
from collections import defaultdict
from util import (find_latest_s3_files, find_latest_s3_file,
                  find_second_latest_s3_file, load_test_results_from_s3)
from indra.statements.statements import Statement


class TestRound():
    def __init__(self, key):
        self.key = key
        self.test_results = load_test_results_from_s3(key)

    def get_statements(self):
        return self.test_results[0]['statements']

    def get_statement_types(self):
        statement_types = defaultdict(int)
        for stmt in self.get_statements():
            statement_types[stmt['type']] += 1
        return statement_types

    def get_agents(self):
        # add agent count

    def get_support(self):
        stmts_evidence = {}
        for stmt in self.get_statements():
            stmts_evidence[stmt['id']] = len(stmt.evidence)
        return stmts_evidence

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

    def get_passed_tests(self):
        passed_tests = []
        for result in self.test_results[1:]:
            if self.has_path(result):
                passed_tests.append(result['english_test'])
        return passed_tests

    def get_path_descriptions(self):
        path_descriptions = []
        for result in self.test_results[1:]:
            if self.has_path(result):
                path_descriptions.append(result['english_result'])
        return path_descriptions

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


def get_deltas(model_name):
    latest_key = find_latest_s3_file('emmaa', f'results/{model_name}/results_',
                                     extension='.json')
    previous_key = find_second_latest_s3_file('emmaa',
                                              f'results/{model_name}/results_',
                                              extension='.json')
    latest_round = TestRound(latest_key)
    previous_round = TestRound(previous_key)