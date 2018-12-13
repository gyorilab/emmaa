"""This module implements the object model for EMMAA model testing."""
from indra.explanation.model_checker import ModelChecker


class TestConnector(object):
    def __init__(self):
        pass

    def applicable(self, model, test):
        return True


class ScopeTestConnector(TestConnector):
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

    def check(self, model):
        mc = ModelChecker(model, [self.stmt])
        res = mc.check_statement(self.stmt)
        return res

    def get_entities(self):
        return self.stmt.agent_list()