"""This module implements the object model for EMMAA model testing."""
import logging
import itertools
from indra.explanation.model_checker import ModelChecker


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
        self.pairs_to_test = []
        self.test_results = {}

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
                self.pairs_to_test.append((model, test))
                logger.info(f'Test {test.stmt} is applicable')
            else:
                logger.info(f'Test {test.stmt} is not applicable')

        logger.info(f'Created {len(self.pairs_to_test)} model-test pairs.')

    def run_tests(self):
        """Run tests for a list of model-test pairs"""
        for idx, (model, test) in enumerate(self.pairs_to_test):
            self.test_results[idx] = test.check(model)


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
    pass


class StatementCheckingTest(EmmaaTest):
    """Represent an EMMAA test condition that checks a PySB-assembled model
    against an INDRA Statement."""
    def __init__(self, stmt):
        self.stmt = stmt

    def check(self, model):
        """Use a model checker to check if a given model satisfies the test."""
        pysb_model = model.assemble_pysb()
        mc = ModelChecker(pysb_model, [self.stmt])
        res = mc.check_statement(self.stmt)
        return res

    def get_entities(self):
        """Return a list of entities that the test checks for."""
        return self.stmt.agent_list()

    def __repr__(self):
        return "%s(stmt=%s)" % (self.__class__.__name__, repr(self.stmt))
