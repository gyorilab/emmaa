from indra.explanation.model_checker import PathResult, ModelChecker
from indra.statements.statements import Statement
from emmaa.model import EmmaaModel
from emmaa.model_tests import (StatementCheckingTest, run_model_tests_from_s3,
                               load_tests_from_s3, ModelManager)
from emmaa.analyze_tests_results import TestRound, StatsGenerator

# Tell nose to not run tests in the imported modules
StatementCheckingTest.__test__ = False
run_model_tests_from_s3.__test__ = False
load_tests_from_s3.__test__ = False
ModelManager.__test__ = False
PathResult.__test__ = False
EmmaaModel.__test__ = False
ModelChecker.__test__ = False
TestRound.__test__ = False
StatsGenerator.__test__ = False
Statement.__test__ = False


def test_load_tests_from_s3():
    tests = load_tests_from_s3('simple_model_test.pkl')
    assert isinstance(tests, list)
    assert len(tests) == 1
    test = tests[0]
    assert isinstance(test, StatementCheckingTest)


def test_run_tests_from_s3():
    (mm, sg) = run_model_tests_from_s3(
        'test', 'simple_model_test.pkl', upload_mm=False,
        upload_results=False, upload_stats=False, registered_queries=False)
    assert isinstance(mm, ModelManager)
    assert isinstance(mm.model, EmmaaModel)
    assert isinstance(mm.model_checker, ModelChecker)
    assert isinstance(mm.test_results[0], PathResult)
    assert isinstance(mm.applicable_tests[0], StatementCheckingTest)
    assert len(mm.applicable_tests) == 1
    assert len(mm.test_results) == 1
    assert isinstance(sg, StatsGenerator)
    assert isinstance(sg.latest_round, TestRound)
    assert isinstance(sg.latest_round.test_results[0], PathResult)
    assert isinstance(sg.latest_round.statements[0], Statement)
    assert len(sg.latest_round.statements) == 2
    assert len(sg.latest_round.test_results) == 1
    assert len(sg.latest_round.tests) == 1
