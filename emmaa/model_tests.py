"""This module implements the object model for EMMAA model testing."""
import itertools


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
        for model, test in itertools.product(self.models, self.tests):
            if test_connector.applicable(model, test):
                self.pairs_to_test.append(model, test)

    def run_tests(self):
        """Run tests for a list of model-test pairs"""
        for model, test in self.pairs_to_test:
            self.test_results[(model, test)] = test.check(model)


class TestConnector(object):
    """Determines if a given test is applicable to a given model."""
    def __init__(self):
        pass

    def applicable(self, model, test):
        """Return True if the test is applicable to the given model."""
        return True


class ScopeTestConnector(TestConnector):
    """Determines applicability of a test to a model by overlap in scope."""
    def applicable(self, model, test):
        model_entities = model.get_entities()
        test_entities = test.get_entities()
        return self._overlap(model_entities, test_entities)

    def _overlap(self, ents1, ents2):
        return True if set(ents1) & set(ents2) else False


class EmmaaTest(object):
    """Represent an EMMAA test condition"""
    pass


class StatementCheckingTest(EmmaaTest):
    """Represent an EMMAA test condition that checks a PySB-assembled model
    against an INDRA Statement."""
    def __init__(self, stmt):
        self.stmt = stmt

    def check(self, model_checker, model):
        """Use a model checker to check if a given model satisfies the test."""
        mc = model_checker(model, [self.stmt])
        res = mc.check_statement(self.stmt)
        return res

    def get_entities(self):
        """Return a list of entities that the test checks for."""
        return self.stmt.agent_list()
