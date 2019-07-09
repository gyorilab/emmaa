import json
import logging
import jsonpickle
import datetime
from collections import defaultdict
from emmaa.util import (find_latest_s3_file, find_second_latest_s3_file,
                        find_latest_s3_files, find_number_of_files_on_s3,
                        make_date_str, get_s3_client)
from indra.statements.statements import Statement
from indra.assemblers.english.assembler import EnglishAssembler
from indra.sources.indra_db_rest.api import get_statement_queries


logger = logging.getLogger(__name__)


CONTENT_TYPE_FUNCTION_MAPPING = {
    'statements': ('get_stmt_hashes', 'get_english_statement_by_hash'),
    'applied_tests': ('get_applied_test_hashes', 'get_english_test_by_hash'),
    'passed_tests': ('get_passed_test_hashes', 'get_english_test_by_hash'),
    'paths': ('get_passed_test_hashes', 'get_path_or_code_by_hash')
}


class TestRound(object):
    """Analyzes the results of one test round.

    Parameters
    ----------
    json_results : list[dict]
        A list of JSON formatted dictionaries to store information about the
        test results. The first dictionary contains information about the model.
        Each consecutive dictionary contains information about a single test
        applied to the model and test results.

    Attributes
    ----------
    statements : list[indra.statements.Statement]
        A list of INDRA Statements used to assemble a model.
    test_results : list[indra.explanation.model_checker.PathResult]
        A list of EMMAA test results.
    tests : list[indra.statements.Statement]
        A list of INDRA Statements used to make EMMAA tests.
    function_mapping : dict
        A dictionary of strings mapping a type of content to a tuple of
        functions necessary to find delta for this type of content. First
        function in a tuple gets a list of all hashes for a given content type,
        while the second returns an English description of a given content type
        for a single hash.
    """
    def __init__(self, json_results):
        self.json_results = json_results
        self.statements = self._get_statements()
        self.test_results = self._get_results()
        self.tests = self._get_tests()
        self.function_mapping = CONTENT_TYPE_FUNCTION_MAPPING
        self.english_test_results = self._get_applied_tests_results()

    @classmethod
    def load_from_s3_key(cls, key):
        client = get_s3_client()
        logger.info(f'Loading test results from {key}')
        obj = client.get_object(Bucket='emmaa', Key=key)
        json_results = json.loads(obj['Body'].read().decode('utf8'))
        test_round = TestRound(json_results)
        return test_round

    # Model Summary Methods
    def get_total_statements(self):
        """Return a total number of statements in a model."""
        total = len(self.statements)
        logger.info(f'An assembled model has {total} statements.')
        return total

    def get_stmt_hashes(self):
        """Return a list of hashes for all statements in a model."""
        return [str(stmt.get_hash(refresh=True)) for stmt in self.statements]

    def get_statement_types(self):
        """Return a sorted list of tuples containing a statement type and a
        number of times a statement of this type occured in a model.
        """
        statement_types = defaultdict(int)
        logger.info('Finding a distribution of statements types.')
        for stmt in self.statements:
            statement_types[type(stmt).__name__] += 1
        return sorted(statement_types.items(), key=lambda x: x[1], reverse=True)

    def get_agent_distribution(self):
        """Return a sorted list of tuples containing an agent name and a number
        of times this agent occured in statements of a model."""
        logger.info('Finding agent distribution among model statements.')
        agent_count = defaultdict(int)
        for stmt in self.statements:
            for agent in stmt.agent_list():
                if agent is not None:
                    agent_count[agent.name] += 1
        return sorted(agent_count.items(), key=lambda x: x[1], reverse=True)

    def get_statements_by_evidence(self):
        """Return a sorted list of tuples containing a statement hash and a
        number of times this statement occured in a model."""
        stmts_evidence = {}
        for stmt in self.statements:
            stmts_evidence[str(stmt.get_hash(refresh=True))] = len(stmt.evidence)
        logger.info('Sorting statements by evidence count.')
        return sorted(stmts_evidence.items(), key=lambda x: x[1], reverse=True)

    def get_english_statements_by_hash(self):
        """Return a dictionary mapping a statement and its English description."""
        stmts_by_hash = {}
        for stmt in self.statements:
            stmts_by_hash[str(stmt.get_hash(refresh=True))] = (
                self.get_english_statement(stmt))
        return stmts_by_hash

    def get_english_statement(self, stmt):
        ea = EnglishAssembler([stmt])
        sentence = ea.make_model()
        link = get_statement_queries([stmt])[0] + '&format=html'
        link_str = f'<a href="{link}">{sentence}</a>'
        return link_str

    def get_english_statement_by_hash(self, stmt_hash):
        return self.get_english_statements_by_hash()[stmt_hash]

    # Test Summary Methods
    def get_applied_test_hashes(self):
        """Return a list of hashes for all applied tests."""
        return list(self.english_test_results.keys())

    def get_passed_test_hashes(self):
        """Return a list of hashes for passed tests."""
        return [test_hash for test_hash in self.english_test_results.keys() if
                self.english_test_results[test_hash][1] == 'Pass']

    def get_total_applied_tests(self):
        """Return a number of all applied tests."""
        total = len(self.tests)
        logger.info(f'{total} tests were applied.')
        return total

    def get_number_passed_tests(self):
        """Return a number of all passed tests."""
        total = len(self.get_passed_test_hashes())
        logger.info(f'{total} tests passed.')
        return total

    def passed_over_total(self):
        """Return a ratio of passed over total tests."""
        return self.get_number_passed_tests()/self.get_total_applied_tests()

    def _get_applied_tests_results(self):
        """Return a dictionary mapping a test hash and a list containing its
        English description, result in Pass/Fail form and either a path if it
        was found or a result code if it was not."""
        tests_by_hash = {}
        logger.info('Retrieving test hashes, english tests and test results.')

        def get_pass_fail(res):
            # Here use result.path_found because we care if the path was found
            # and do not care about path length
            if res.path_found:
                return 'Pass'
            else:
                return 'Fail'

        for ix, test in enumerate(self.tests):
            test_hash = str(test.get_hash(refresh=True))
            result = self.test_results[ix]
            tests_by_hash[test_hash] = [
                self.get_english_statement(test),
                get_pass_fail(result),
                self.get_path_or_code_by_hash(test_hash)]

        return tests_by_hash

    def get_path_descriptions(self):
        """Return a dictionary mapping a test hash and an English description
        of a path found.
        """
        english_paths = {}
        for ix, result in enumerate(self.test_results):
            # Here we use result.paths because we can only get a description if
            # a path does not exceed max length
            if result.paths:
                paths = []
                for path in self.json_results[ix+1]['english_path']:
                    links = []
                    for (sentence, link) in path:
                        link_str = f'<a href="{link}">{sentence}</a>'
                        links.append(link_str)
                    paths.append(links)
                    english_paths[str(self.tests[ix].get_hash(refresh=True))] = paths
        return english_paths

    def get_english_codes(self):
        """Return a dictionary mapping a test hash and an English description
        of a result code.
        """
        english_codes = {}
        for ix, result in enumerate(self.test_results):
            (sentence, link) = self.json_results[ix+1]['english_code'][0][0]
            english_codes[str(self.tests[ix].get_hash(refresh=True))] = (
                [[f'<a href="{link}">{sentence}</a>']])
        return english_codes

    def get_english_test_by_hash(self, test_hash):
        return self.english_test_results[test_hash][0]

    def get_pass_fail_by_hash(self, test_hash):
        return self.english_test_results[test_hash][1]

    def get_path_or_code_by_hash(self, test_hash):
        # If we have a path description return it, otherwise return code
        try:
            result = self.get_path_descriptions()[test_hash]
        except KeyError:
            result = self.get_english_codes()[test_hash]
        return result

    # Methods to find delta
    def find_numeric_delta(self, other_round, one_round_numeric_func):
        """Find a numeric delta between two rounds using a passed function.

        Parameters
        ----------
        other_round : emmaa.analyze_tests_results.TestRound
            A different instance of a TestRound
        one_round_numeric_function : str
            A name of a method to calculate delta. Accepted values:
            - get_total_statements
            - get_total_applied_tests
            - get_number_passed_tests
            - passed_over_total

        Returns
        -------
        delta : int or float
            Difference between return values of one_round_numeric_function
            of two given test rounds.
        """
        logger.info(f'Calculating numeric delta using {one_round_numeric_func}'
                    ' method')
        delta = (getattr(self, one_round_numeric_func)()
                 - getattr(other_round, one_round_numeric_func)())
        return delta

    def find_content_delta(self, other_round, content_type, add_result=False):
        """Return a dictionary of changed items of a given content type. This
        method makes use of self.function_mapping dictionary.

        Parameters
        ----------
        other_round : emmaa.analyze_tests_results.TestRound
            A different instance of a TestRound
        content_type : str
            A type of the content to find delta. Accepted values:
            - statements
            - applied_tests
            - passed_tests
            - paths
        add_result : boolean
            Optionally add a Pass/Fail format result to a test.

        Returns
        -------
            A dictionary containing lists of added and removed items of a given
            content type between two test rounds. If add_result is set to True,
            a dictionary will contain lists of tuples where each tuple has an
            item and a result in Pass/Fail format.
        """
        logger.info(f'Finding a content delta for {content_type}.')
        # First we need to find hashes of objects we want to compare for 
        # latest and previous rounds
        latest_hashes = getattr(self, self.function_mapping[content_type][0])()
        logger.info(f'Found {len(latest_hashes)} hashes in current round.')
        previous_hashes = getattr(
            other_round, other_round.function_mapping[content_type][0])()
        logger.info(f'Found {len(previous_hashes)} hashes in other round.')
        # Find hashes unique for each of the rounds - this is delta
        added_hashes = list(set(latest_hashes) - set(previous_hashes))
        removed_hashes = list(set(previous_hashes) - set(latest_hashes))

        def get_item(tr, item_hash):
            # Get an instance of an object given its hash
            return getattr(
                    tr, tr.function_mapping[content_type][1])(item_hash)

        # Optionally add pass/fail status (applicable for tests)
        if add_result:
            added_items = [(get_item(self, item_hash),
                            self.get_pass_fail_by_hash(item_hash))
                           for item_hash in added_hashes]
            removed_items = [(get_item(other_round, item_hash),
                              other_round.get_pass_fail_by_hash(item_hash))
                             for item_hash in removed_hashes]
        # Get lists of items added and removed in the latest round
        else:
            added_items = [
                get_item(self, item_hash) for item_hash in added_hashes]
            removed_items = [
                get_item(other_round, item_hash) for item_hash in
                removed_hashes]
        logger.info(f'Found {len(added_items)} added and {len(removed_items)} '
                    f'removed items of {content_type}.')
        return {'added': added_items, 'removed': removed_items}

    # Helping methods
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


class StatsGenerator(object):
    """Generates statistic for a given test round.

    Parameters
    ----------
    model_name : str
        A name of a model the tests were run against.
    latest_round : emmaa.analyze_tests_results.TestRound
        An instance of a TestRound to generate statistics for. If not given,
        will be generated by loading test results from s3.
    previous_round : emmaa.analyze_tests_results.TestRound
        A different instance of a TestRound to find delta between two rounds.
        If not given, will be generated by loading test results from s3.

    Attributes
    ----------
    json_stats : dict
        A JSON-formatted dictionary containing test model and test statistics.
    earlier_json_stats : list[dict]
        A list of JSON-formatted dictionaries containing test model and test
        statistics for earlier test rounds.
    """

    def __init__(self, model_name, latest_round=None, previous_round=None,
                 previous_json_stats=None):
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
        if not previous_json_stats:
            self.previous_json_stats = self._get_previous_json_stats()
        else:
            self.previous_json_stats = previous_json_stats

    def make_stats(self):
        """Check if two latest test rounds were found and add statistics to
        json_stats dictionary. If both latest round and previous round
        were passed or found on s3, a dictionary will have four key-value
        pairs: model_summary, test_round_summary, model_delta, and tests_delta.
        """
        if not self.latest_round:
            logger.info(f'Latest round for {self.model_name} is not found.')
            return
        logger.info(f'Generating stats for {self.model_name}.')
        self.make_model_summary()
        self.make_test_summary()
        self.make_model_delta()
        self.make_tests_delta()
        self.make_changes_over_time()
        
    def make_model_summary(self):
        """Add latest model state summary to json_stats."""
        logger.info(f'Generating model summary for {self.model_name}.')
        self.json_stats['model_summary'] = {
            'model_name': self.model_name,
            'number_of_statements': self.latest_round.get_total_statements(),
            'stmts_type_distr': self.latest_round.get_statement_types(),
            'agent_distr': self.latest_round.get_agent_distribution(),
            'stmts_by_evidence': self.latest_round.get_statements_by_evidence(),
            'english_stmts': self.latest_round.get_english_statements_by_hash()
        }

    def make_test_summary(self):
        """Add latest test round summary to json_stats."""
        logger.info(f'Generating test summary for {self.model_name}.')
        self.json_stats['test_round_summary'] = {
            'number_applied_tests': self.latest_round.get_total_applied_tests(),
            'number_passed_tests': self.latest_round.get_number_passed_tests(),
            'passed_ratio': self.latest_round.passed_over_total(),
            'tests_by_hash': self.latest_round.english_test_results,
            'passed_tests': self.latest_round.get_passed_test_hashes(),
            'paths': self.latest_round.get_path_descriptions()
        }

    def make_model_delta(self):
        """Add model delta between two latest model states to json_stats."""
        logger.info(f'Generating model delta for {self.model_name}.')
        if not self.previous_round:
            self.json_stats['model_delta'] = {
                'number_of_statements_delta': 0,
                'statements_delta': {'added': [], 'removed': []}
            }
        else:
            self.json_stats['model_delta'] = {
                'number_of_statements_delta': (
                    self.latest_round.find_numeric_delta(
                        self.previous_round, 'get_total_statements')),
                'statements_delta': self.latest_round.find_content_delta(
                    self.previous_round, 'statements')
            }

    def make_tests_delta(self):
        """Add tests delta between two latest test rounds to json_stats."""
        logger.info(f'Generating tests delta for {self.model_name}.')
        if not self.previous_round:
            self.json_stats['tests_delta'] = {
                'number_applied_tests_delta': 0,
                'number_passed_tests_delta': 0,
                'passed_ratio_delta': 0,
                'applied_tests_delta': {'added': [], 'removed': []},
                'pass_fail_delta': {'added': [], 'removed': []},
                'new_paths': {'added': [], 'removed': []}
            }
        else:
            self.json_stats['tests_delta'] = {
                'number_applied_tests_delta': (
                    self.latest_round.find_numeric_delta(
                        self.previous_round, 'get_total_applied_tests')),
                'number_passed_tests_delta': (
                    self.latest_round.find_numeric_delta(
                        self.previous_round, 'get_number_passed_tests')),
                'passed_ratio_delta': self.latest_round.find_numeric_delta(
                    self.previous_round, 'passed_over_total'),
                'applied_tests_delta': self.latest_round.find_content_delta(
                    self.previous_round, 'applied_tests', add_result=True),
                'pass_fail_delta': self.latest_round.find_content_delta(
                    self.previous_round, 'passed_tests'),
                'new_paths': self.latest_round.find_content_delta(
                    self.previous_round, 'paths')
            }

    def make_changes_over_time(self):
        """Add changes to model and tests over time to json_stats."""
        logger.info(f'Comparing changes over time for {self.model_name}.')
        self.json_stats['changes_over_time'] = {
            'number_of_statements': self.get_over_time(
                'model_summary', 'number_of_statements'),
            'number_applied_tests': self.get_over_time(
                'test_round_summary', 'number_applied_tests'),
            'number_passed_tests': self.get_over_time(
                'test_round_summary', 'number_passed_tests'),
            'passed_ratio': self.get_over_time(
                'test_round_summary', 'passed_ratio'),
            'dates': self.get_dates()
        }

    def get_over_time(self, section, metrics):
        logger.info(f'Getting changes over time in {metrics} '
                    f'for {self.model_name}.')
        if not self.previous_json_stats:
            previous_data = []
        else:
            previous_data = (
                self.previous_json_stats['changes_over_time'][metrics])
        previous_data.append(self.json_stats[section][metrics])
        return previous_data

    def get_dates(self):
        if not self.previous_json_stats:
            previous_dates = []
        else:
            previous_dates = (
                self.previous_json_stats['changes_over_time']['dates'])
        previous_dates.append(make_date_str())
        return previous_dates

    def save_to_s3(self):
        json_stats_str = json.dumps(self.json_stats, indent=1)
        client = get_s3_client()
        date_str = make_date_str()
        stats_key = f'stats/{self.model_name}/stats_{date_str}.json'
        logger.info(f'Uploading test round statistics to {stats_key}')
        client.put_object(Bucket='emmaa', Key=stats_key,
                          Body=json_stats_str.encode('utf8'))

    def _get_latest_round(self):
        latest_key = find_latest_s3_file(
            'emmaa', f'results/{self.model_name}/results_', extension='.json')
        if latest_key is None:
            logger.info(f'Could not find a key to the latest test results '
                        f'for {self.model_name} model.')
            return
        tr = TestRound.load_from_s3_key(latest_key)
        return tr

    def _get_previous_round(self):
        previous_key = find_second_latest_s3_file(
            'emmaa', f'results/{self.model_name}/results_', extension='.json')
        if previous_key is None:
            logger.info(f'Could not find a key to the previous test results '
                        f'for {self.model_name} model.')
            return
        tr = TestRound.load_from_s3_key(previous_key)
        return tr

    def _get_previous_json_stats(self):
        key = find_latest_s3_file(
            'emmaa', f'stats/{self.model_name}/stats_', extension='.json')
        if key is None:
            logger.info(f'Could not find a key to the previous statistics '
                        f'for {self.model_name} model.')
            return
        client = get_s3_client()
        logger.info(f'Loading earlier statistics from {key}')
        obj = client.get_object(Bucket='emmaa', Key=key)
        previous_json_stats = json.loads(obj['Body'].read().decode('utf8'))
        return previous_json_stats
