from nose.plugins.attrib import attr

from indra.statements import Activation, Agent
from indra.explanation.model_checker import PathResult, PysbModelChecker, \
    PybelModelChecker, SignedGraphModelChecker, UnsignedGraphModelChecker
from indra.statements.statements import Statement, Agent
from emmaa.model import EmmaaModel
from emmaa.model_tests import StatementCheckingTest, ModelManager, \
    ScopeTestConnector, TestManager
from emmaa.analyze_tests_results import TestRound, StatsGenerator
from emmaa.tests.test_model import create_model


# Tell nose to not run tests in the imported modules
StatementCheckingTest.__test__ = False
TestRound.__test__ = False
ScopeTestConnector.__test__ = False
TestManager.__test__ = False


def test_model_manager_structure():
    model = create_model()
    mm = ModelManager(model)
    assert isinstance(mm, ModelManager)
    assert isinstance(mm.model, EmmaaModel)
    assert mm.model.name == 'test'
    assert len(mm.mc_types) == 4, len(mm.mc_types)
    assert len(mm.mc_types['pysb']) == 3
    assert isinstance(mm.mc_types['pysb']['model_checker'], PysbModelChecker)
    assert isinstance(mm.mc_types['pybel']['model_checker'], PybelModelChecker)
    assert isinstance(
        mm.mc_types['signed_graph']['model_checker'], SignedGraphModelChecker)
    assert isinstance(
        mm.mc_types['unsigned_graph']['model_checker'],
        UnsignedGraphModelChecker)
    assert isinstance(mm.entities[0], Agent)
    assert isinstance(mm.date_str, str)


def test_run_tests():
    model = create_model()
    tests = [StatementCheckingTest(
             Activation(Agent('BRAF', db_refs={'HGNC': '1097'}),
                        Agent('MAPK1', db_refs={'UP': 'P28482'})))]
    mm = ModelManager(model)
    tm = TestManager([mm], tests)
    tm.make_tests(ScopeTestConnector())
    tm.run_tests()
    assert len(mm.applicable_tests) == 1
    assert isinstance(mm.applicable_tests[0], StatementCheckingTest)
    assert len(mm.mc_types['pysb']['test_results']) == 1
    assert len(mm.mc_types['pybel']['test_results']) == 1
    assert len(mm.mc_types['signed_graph']['test_results']) == 1
    assert len(mm.mc_types['unsigned_graph']['test_results']) == 1
    assert isinstance(mm.mc_types['pysb']['test_results'][0], PathResult)
