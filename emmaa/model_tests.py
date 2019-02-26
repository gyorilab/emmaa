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
from emmaa.model import EmmaaModel
from emmaa.util import make_date_str, get_s3_client


logger = logging.getLogger(__name__)


class TestManager(object):
    """Manager to generate and run a set of tests on a set of models.

    Parameters
    ----------
    models : list[emmaa.model.EmmaaModel]
        A list of EMMAA models
    tests : list[emmaa.model_tests.EmmaaTest]
        A list of EMMAA tests
    """
    def __init__(self, models, tests):
        self.models = models
        self.tests = tests
        # self.pairs_to_test = []
        # self.test_results = []
        self.model_entities = {model: model.get_entities() for model in 
                               self.models}
        self.test_entities = {test: test.get_entities() for test in self.tests}
        self.model_to_tests = defaultdict(list)
        self.test_to_results = defaultdict(list)
        # model to results or test to results?

    def make_tests(self, test_connector):
        """Generate a list of model-test pairs with a given test connector

        Parameters
        ----------
        test_connector : emmaa.model_tests.TestConnector
            A TestConnector object to use for connecting models to tests.
        """
        logger.info(f'Checking applicability of {len(self.tests)} tests to '
                    f'{len(self.models)} models')
        for model, test in itertools.product(self.models, self.tests):
            logger.info(f'Checking applicability of test {test.stmt}')
            if test_connector.applicable(model, test):
                # self.pairs_to_test.append((model, test))
                self.model_to_tests[model].append(test)
                logger.info(f'Test {test.stmt} is applicable')
            else:
                logger.info(f'Test {test.stmt} is not applicable')
        # logger.info(f'Created {len(self.pairs_to_test)} model-test pairs.')
        logger.info(f'Created tests for {len(self.model_to_tests)} models.')
        for model in self.model_to_tests.keys():
            logger.info(f'Created {len(self.model_to_tests[model])} tests for {model.name} model.')

    # def run_tests(self):
    #     """Run tests for a list of model-test pairs"""
    #     for (model, test) in self.pairs_to_test:
    #         self.test_results.append(test.check(model))

    def run_tests(self):
        """Run tests for a list of model-test pairs"""
        for model in self.model_to_tests.keys():
            pysb_model = model.assemble_pysb()
            # model to results or test to results?
            for test in self.model_to_tests[model]:
                self.test_to_results[test].append(test.check(pysb_model))

    def results_to_json(self):
        # TODO
        # also convert this into using model_to_tests dict
        # problem - current indexing works only for cases when we have just one model
        # possible solutions - make test_results also a dict
        pickler = jsonpickle.pickler.Pickler()
        results_json = []
        for model, tests in self.model_to_tests.items():
            # model to test to result
            for ix, test in enumerate(tests):
                results_json.append({
                   'model_name': model.name,
                   'test_type': test.__class__.__name__,
                   'test_json': test.to_json(),
                   'result_json': pickler.flatten(self.test_to_results[test][ix])})
        # for ix, (model, test) in enumerate(self.pairs_to_test):
        #     results_json.append({
        #            'model_name': model.name,
        #            'test_type': test.__class__.__name__,
        #            'test_json': test.to_json(),
        #            'result_json': pickler.flatten(self.test_results[ix])})
        return results_json


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
        model_entities = model.get_entities()
        test_entities = test.get_entities()
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
    # def __init__(self, stmt):
    #     self.stmt = stmt

    # def check(self, model):
    #     """Use a model checker to check if a given model satisfies the test."""
    #     pysb_model = model.assemble_pysb()
    #     mc = ModelChecker(pysb_model, [self.stmt])
    #     res = mc.check_statement(self.stmt)
    #     return res

    def __init__(self, stmt):
        self.stmt = stmt

    def check(self, pysb_model):
        """Use a model checker to check if a given model satisfies the test."""
        mc = ModelChecker(pysb_model, [self.stmt])
        res = mc.check_statement(self.stmt)
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


def run_model_tests_from_s3(model_name, test_name, upload_results=True):
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
    emmaa.model_tests.TestManager
        Instance of TestManager containing the model/test pairs and the
        test results.
    """
    model = EmmaaModel.load_from_s3(model_name)
    tests = load_tests_from_s3(test_name)
    tm = TestManager([model], tests)
    tm.make_tests(ScopeTestConnector())
    tm.run_tests()
    results_json_dict = tm.results_to_json()
    results_json_str = json.dumps(results_json_dict)
    # Optionally upload test results to S3
    if upload_results:
        client = get_s3_client()
        date_str = make_date_str(datetime.datetime.now())
        result_key = f'results/{model_name}/results_{date_str}.json'
        logger.info(f'Uploading test results to {result_key}')
        client.put_object(Bucket='emmaa', Key=result_key,
                          Body=results_json_str.encode('utf8'))
    return tm

