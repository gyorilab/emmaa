import json
import logging
import jsonpickle
from collections import defaultdict
from emmaa.util import (find_latest_s3_file, find_second_latest_s3_file,
                        get_s3_client)
from indra.statements.statements import Statement
from indra.assemblers.english.assembler import EnglishAssembler


logger = logging.getLogger(__name__)


CONTENT_TYPE_FUNCTION_MAPPING = {
    'statements': ('get_stmt_hashes', 'get_english_statement_by_hash'),
    'applied_tests': ('get_applied_test_hashes', 'get_english_test_by_hash'),
    'passed_tests': ('get_passed_test_hashes', 'get_english_test_by_hash'),
    'paths': ('get_passed_test_hashes', 'get_path_by_hash')
}


class TestRound(object):
    def __init__(self, json_results):
        self.json_results = json_results
        self.statements = self._get_statements()
        self.test_results = self._get_results()
        self.tests = self._get_tests()
        self.function_mapping = CONTENT_TYPE_FUNCTION_MAPPING

    @classmethod
    def load_from_s3_key(cls, key):
        client = get_s3_client()
        logger.info(f'Loading test results from {key}')
        obj = client.get_object(Bucket='emmaa', Key=key)
        json_results = json.loads(obj['Body'].read().decode('utf8'))
        test_round = TestRound(json_results)
        return test_round

    def _get_statements(self):
        serialized_stmts = self.json_results[0]['statements']
        return [Statement._from_json(stmt) for stmt in serialized_stmts]

    def _get_results(self):
        unpickler = jsonpickle.unpickler.Unpickler()
        test_results = [unpickler.restore(result['result_json'])
                        for result in self.json_results[1:]]
        return test_results

    def _get_tests(self):
        tests = [Statement._from_json(res['test_json'])
                 for res in self.json_results[1:]]
        return tests

    # Model Summary
    def get_total_statements(self):
        return len(self.statements)

    def get_stmt_hashes(self):
        return [stmt.get_hash() for stmt in self.statements]

    def get_statement_types(self):
        statement_types = defaultdict(int)
        for stmt in self.statements:
            statement_types[type(stmt).__name__] += 1
        return sorted(statement_types.items(), key=lambda x: x[1], reverse=True)

    def get_agent_distribution(self):
        agent_count = defaultdict(int)
        for stmt in self.statements:
            for agent in stmt.agent_list():
                if agent is not None:
                    agent_count[agent.name] += 1
        return sorted(agent_count.items(), key=lambda x: x[1], reverse=True)

    def get_statements_by_evidence(self):
        stmts_evidence = {}
        for stmt in self.statements:
            stmts_evidence[stmt.get_hash()] = len(stmt.evidence)
        return sorted(stmts_evidence.items(), key=lambda x: x[1], reverse=True)

    def get_english_statement(self, stmt):
        ea = EnglishAssembler([stmt])
        return ea.make_model()

    def get_english_statements_by_hash(self):
        stmts_by_hash = {}
        for stmt in self.statements:
            stmts_by_hash[stmt.get_hash()] = self.get_english_statement(stmt)
        return stmts_by_hash

    def get_english_statement_by_hash(self, stmt_hash):
        return self.get_english_statements_by_hash()[stmt_hash]

    # Test Summary
    def get_applied_test_hashes(self):
        return [test.get_hash() for test in self.tests]

    def get_passed_test_hashes(self):
        passed_tests = []
        for ix, result in enumerate(self.test_results):
            if result.path_found:
                passed_tests.append(self.tests[ix].get_hash())
        return passed_tests

    def get_total_applied_tests(self):
        return len(self.tests)

    def get_number_passed_tests(self):
        return len(self.get_passed_test_hashes())

    def passed_over_total(self):
        return self.get_number_passed_tests()/self.get_total_applied_tests()

    def get_english_tests(self):
        tests_by_hash = {}
        for test in self.tests:
            tests_by_hash[test.get_hash()] = self.get_english_statement(test)
        return tests_by_hash

    def get_english_test_by_hash(self, test_hash):
        return self.get_english_tests()[test_hash]

    def get_path_descriptions(self):
        paths = {}
        for ix, result in enumerate(self.test_results):
            if result.path_found:
                paths[self.tests[ix].get_hash()] = self.json_results[ix+1]['english_result']
        return paths

    def get_path_by_hash(self, test_hash):
        return self.get_path_descriptions()[test_hash]

    # Deltas
    def find_numeric_delta(self, other_round, one_round_numeric_func):
        # return self.one_round_func() - other_round.one_round_numeric_func()
        delta = (getattr(self, one_round_numeric_func)()
                 - getattr(other_round, one_round_numeric_func)())
        return delta

    def find_content_delta(self, other_round, content_type):
        """content_type: statements, applied_tests, passed_tests, paths
        """
        latest_ids = getattr(self, self.function_mapping[content_type][0])()
        previous_ids = getattr(other_round,
                               other_round.function_mapping[content_type][0])()
        added_ids = list(set(latest_ids) - set(previous_ids))
        removed_ids = list(set(previous_ids) - set(latest_ids))
        added_items = [getattr(
            self, self.function_mapping[content_type][1])(item_id)
            for item_id in added_ids]
        removed_items = [getattr(
            other_round,
            other_round.function_mapping[content_type][1])(item_id)
            for item_id in removed_ids]
        return {'added': added_items, 'removed': removed_items}


class StatsGenerator(object):
    def __init__(self, model_name, latest_round=None, previous_round=None):
        self.model_name = model_name
        if not latest_round:
            self.latest_round = self._get_latest_round()
        else:
            self.latest_round = latest_round
        if not previous_round:
            self.previous_round = self._get_previous_round()
        else:
            self.previous_round = previous_round
        self.json_stats = {}

    def _get_latest_round(self):
        tr = TestRound.load_from_s3_key(find_latest_s3_file(
            'emmaa', f'results/{self.model_name}/results_', extension='.json'))
        return tr

    def _get_previous_round(self):
        tr = TestRound.load_from_s3_key(find_second_latest_s3_file(
            'emmaa', f'results/{self.model_name}/results_', extension='.json'))
        return tr
        
    def make_model_summary(self):
        self.json_stats['model_summary'] = {
            'model_name': self.model_name,
            'number_of_statements': self.latest_round.get_total_statements(),
            'stmts_type_distr': self.latest_round.get_statement_types(),
            'agent_distr': self.latest_round.get_agent_distribution(),
            'stmts_by_evidence': self.latest_round.get_statements_by_evidence(),
            'english_stmts': self.latest_round.get_english_statements_by_hash()
        }

    def make_test_summary(self):
        self.json_stats['test_round_summary'] = {
            'number_applied_tests': self.latest_round.get_total_applied_tests(),
            'number_passed_tests': self.latest_round.get_number_passed_tests(),
            'passed_ratio': self.latest_round.passed_over_total(),
            'tests_by_id': self.latest_round.get_english_tests(),
            'passed_tests': self.latest_round.get_passed_test_hashes(),
            'paths': self.latest_round.get_path_descriptions()
        }

    def make_model_delta(self):
        self.json_stats['model_delta'] = {
            'number_of_statements_delta': self.latest_round.find_numeric_delta(
                self.previous_round, 'get_total_statements'),
            'statements_delta': self.latest_round.find_content_delta(
                self.previous_round, 'statements')
        }

    def make_tests_delta(self):
        self.json_stats['tests_delta'] = {
            'number_applied_tests_delta': self.latest_round.find_numeric_delta(
                self.previous_round, 'get_total_applied_tests'),
            'number_passed_tests_delta': self.latest_round.find_numeric_delta(
                self.previous_round, 'get_number_passed_tests'),
            'passed_ratio_delta': self.latest_round.find_numeric_delta(
                self.previous_round, 'passed_over_total'),
            'applied_tests_delta': self.latest_round.find_content_delta(
                self.previous_round, 'applied_tests'),
            'pass_fail_delta': self.latest_round.find_content_delta(
                self.previous_round, 'passed_tests'),
            'new_paths': self.latest_round.find_content_delta(
                self.previous_round, 'paths')
        }