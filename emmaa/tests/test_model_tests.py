from indra.explanation.model_checker import PathResult
from emmaa.model_tests import (StatementCheckingTest, run_model_tests_from_s3,
                               load_tests_from_s3, TestManager)

# Tell nose to not run tests in the imported modules
StatementCheckingTest.__test__ = False
run_model_tests_from_s3.__test__ = False
load_tests_from_s3.__test__ = False
TestManager.__test__ = False
PathResult.__test__ = False


def test_load_tests_from_s3():
    tests = load_tests_from_s3('simple_model_test.pkl')
    assert isinstance(tests, list)
    assert len(tests) == 1
    test = tests[0]
    assert isinstance(test, StatementCheckingTest)


def test_run_tests_from_s3():
    tm = run_model_tests_from_s3('test', 'simple_model_test.pkl',
                                 upload_results=False)
    assert isinstance(tm, TestManager)
    assert len(tm.model_managers[0].applicable_tests) == 1
    assert len(tm.model_managers[0].test_results) == 1
    assert isinstance(tm.model_managers[0].test_results[0], PathResult)