"""This module implements the object model for EMMAA model testing."""
import json
import boto3
import pickle
import logging
import datetime
import itertools
import jsonpickle
from collections import defaultdict
from indra.explanation.model_checker import ModelChecker
from indra.explanation.reporting import stmts_from_path
from indra.assemblers.english.assembler import EnglishAssembler
from emmaa.model import EmmaaModel
from emmaa.util import make_date_str, get_s3_client
from emmaa.analyze_tests_results import TestRound, StatsGenerator


logger = logging.getLogger(__name__)


class ModelManager(object):
    """Manager to generate and store properties of a model and relevant tests.

    Parameters
    ----------
    model : emmaa.model.EmmaaModel
        EMMAA model

    Attributes
    ----------
    pysb_model : emmaa.model.EmmaaModel
        PySB model assembled from EMMAA model
    entities : list[indra.statements.agent.Agent]
        A list of entities of EMMAA model
    applicable_tests : list[emmaa.model_tests.EmmaaTest]
        A list of EMMAA tests applicable for given EMMAA model
    test_results : list[indra.explanation.model_checker.PathResult]
        A list of EMMAA test results
    model_checker : indra.explanation.model_checker.ModelChecker
        A ModelChecker to check PySB model
    """
    def __init__(self, model, belief_cutoff=None):
        self.model = model
        self.pysb_model = self.model.assemble_pysb(belief_cutoff=belief_cutoff)
        self.entities = self.model.get_entities()
        self.applicable_tests = []
        self.test_results = []
        self.model_checker = ModelChecker(self.pysb_model)

    def get_im(self):
        """Get the influence map for the model."""
        self.model_checker.get_im(self.pysb_model)

    def add_test(self, test):
        """Add a test to a list of applicable tests."""
        self.applicable_tests.append(test)

    def add_result(self, result):
        """Add a result to a list of results."""
        self.test_results.append(result)

    def run_one_test(self, test):
        """Run one test. Recommended for testing only.
        Use run_tests() to run all tests.
        """
        return test.check(self.model_checker, self.pysb_model)

    def run_tests(self):
        """Run all applicable tests for the model."""
        self.model_checker.add_statements([test.stmt for test in
                                           self.applicable_tests])
        self.get_im()
        results = self.model_checker.check_model()
        for (stmt, result) in results:
            self.add_result(result)

    def make_english_result(self, result):
        """Create an English description of a path."""
        stmts = stmts_from_path(result.paths[0], self.pysb_model,
                                self.model.assembled_stmts)
        sentences = []
        for stmt in stmts:
            ea = EnglishAssembler([stmt])
            sentences.append(ea.make_model())
        return sentences

    def has_path(self, result):
        """Check if a path was found."""
        return result.path_found

    def get_english_result(self, result):
        """Get English description of a path if it was found.
        Return an empty string otherwise.
        """
        if self.has_path(result):
            return self.make_english_result(result)
        return []

    def assembled_stmts_to_json(self):
        """Put assembled statements to JSON format."""
        stmts = []
        for stmt in self.model.assembled_stmts:
            stmts.append(stmt.to_json())
        return stmts

    def results_to_json(self):
        """Put test results to json format."""
        pickler = jsonpickle.pickler.Pickler()
        results_json = []
        results_json.append({                   
            'model_name': self.model.name,
            'statements': self.assembled_stmts_to_json()})
        for ix, test in enumerate(self.applicable_tests):
            results_json.append({
                   'test_type': test.__class__.__name__,
                   'test_json': test.to_json(),
                   'result_json': pickler.flatten(self.test_results[ix]),
                   'english_result': self.get_english_result(
                                     self.test_results[ix])})
        return results_json


class TestManager(object):
    """Manager to generate and run a set of tests on a set of models.

    Parameters
    ----------
    model_managers : list[emmaa.model_tests.ModelManager]
        A list of ModelManager objects
    tests : list[emmaa.model_tests.EmmaaTest]
        A list of EMMAA tests
    """
    def __init__(self, model_managers, tests):
        self.model_managers = model_managers
        self.tests = tests

    def make_tests(self, test_connector):
        """Generate a list of applicable tests for each model with a given test
        connector.

        Parameters
        ----------
        test_connector : emmaa.model_tests.TestConnector
            A TestConnector object to use for connecting models to tests.
        """
        logger.info(f'Checking applicability of {len(self.tests)} tests to '
                    f'{len(self.model_managers)} models')
        for model_manager, test in itertools.product(self.model_managers,
                                                     self.tests):
            logger.info(f'Checking applicability of test {test.stmt}')
            if test_connector.applicable(model_manager, test):
                model_manager.add_test(test)
                logger.info(f'Test {test.stmt} is applicable')
            else:
                logger.info(f'Test {test.stmt} is not applicable')
        logger.info(f'Created tests for {len(self.model_managers)} models.')
        for model_manager in self.model_managers:
            logger.info(f'Created {len(model_manager.applicable_tests)} tests '
                        f'for {model_manager.model.name} model.')

    def run_tests(self):
        """Run tests for a list of model-test pairs"""
        for model_manager in self.model_managers:
            model_manager.run_tests()


class TestConnector(object):
    """Determines if a given test is applicable to a given model."""
    def __init__(self):
        pass

    @staticmethod
    def applicable(model, test):
        """Return True if the test is applicable to the given model."""
        return True


class ScopeTestConnector(TestConnector):
    """Determines applicability of a test to a model by overlap in scope."""
    @staticmethod
    def applicable(model, test):
        """Return True of all test entities are in the set of model entities"""
        model_entities = model.entities
        test_entities = test.get_entities()
        # TODO
        # After adding entities as an attribute to StatementCheckingTest(), use
        # test_entities = test.entities
        return ScopeTestConnector._overlap(model_entities, test_entities)

    @staticmethod
    def _overlap(model_entities, test_entities):
        me_names = {e.name for e in model_entities}
        te_names = {e.name for e in test_entities}
        # If all test entities are in model entities, we get an empty set here
        # so we return True
        return not te_names - me_names


class EmmaaTest(object):
    """Represent an EMMAA test condition"""
    def get_entities(self):
        """Return a list of entities that the test checks for."""
        raise NotImplementedError()


class StatementCheckingTest(EmmaaTest):
    """Represent an EMMAA test condition that checks a PySB-assembled model
    against an INDRA Statement."""
    def __init__(self, stmt):
        self.stmt = stmt
        # TODO
        # Add entities as a property if we can reload tests on s3.
        # self.entities = self.get_entities()

    def check(self, model_checker, pysb_model):
        """Use a model checker to check if a given model satisfies the test."""
        res = model_checker.check_statement(self.stmt)
        return res

    def get_entities(self):
        """Return a list of entities that the test checks for."""
        return self.stmt.agent_list()

    def to_json(self):
        return self.stmt.to_json()

    def __repr__(self):
        return "%s(stmt=%s)" % (self.__class__.__name__, repr(self.stmt))


def load_tests_from_s3(test_name):
    """Load Emmaa Tests with the given name from S3.

    Parameters
    ----------
    test_name : str
        Looks for a test file in the emmaa bucket on S3 with key
        'tests/{test_name}'.

    Return
    ------
    list of EmmaaTest
        List of EmmaaTest objects loaded from S3.
    """
    client = get_s3_client()
    test_key = f'tests/{test_name}'
    logger.info(f'Loading tests from {test_key}')
    obj = client.get_object(Bucket='emmaa', Key=test_key)
    tests = pickle.loads(obj['Body'].read())
    return tests


def run_model_tests_from_s3(model_name, test_name, belief_cutoff=0.8,
                            upload_results=True, upload_stats=True):
    """Run a given set of tests on a given model, both loaded from S3.

    After loading both the model and the set of tests, model/test overlap
    is determined using a ScopeTestConnector and tests are run.


    Parameters
    ----------
    model_name : str
        Name of EmmaaModel to load from S3.
    test_name : str
        Name of test file to load from S3.
    upload_results : bool
        Whether to upload test results to S3 in JSON format. Can be set
        to False when running tests.

    Returns
    -------
    emmaa.model_tests.ModelManager
        Instance of ModelManager containing the model data, list of applied
        tests and the test results.
    emmaa.analyze_test_results.StatsGenerator
        Instance of StatsGenerator containing statistics about model and test.
    """
    model = EmmaaModel.load_from_s3(model_name)
    tests = load_tests_from_s3(test_name)
    mm = ModelManager(model, belief_cutoff=belief_cutoff)
    tm = TestManager([mm], tests)
    tm.make_tests(ScopeTestConnector())
    tm.run_tests()
    results_json_dict = mm.results_to_json()
    results_json_str = json.dumps(results_json_dict)
    # Optionally upload test results to S3
    if upload_results:
        client = get_s3_client()
        date_str = make_date_str(datetime.datetime.now())
        result_key = f'results/{model_name}/results_{date_str}.json'
        logger.info(f'Uploading test results to {result_key}')
        client.put_object(Bucket='emmaa', Key=result_key,
                          Body=results_json_str.encode('utf8'))
    tr = TestRound(results_json_dict)
    sg = StatsGenerator(model_name, latest_round=tr)
    sg.make_stats()
    stats_json_dict = sg.json_stats
    # Optionally upload statistics to S3
    if upload_stats:
        sg.save_to_s3()
    return (mm, sg)