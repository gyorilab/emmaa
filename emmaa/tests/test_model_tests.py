from emmaa.model_tests import (StatementCheckingTest, run_tests_from_s3,
                               load_tests_from_s3)

def test_load_tests_from_s3():
    tests = load_tests_from_s3('simple_model_test.pkl')
    assert isinstance(tests, list)
    assert len(tests) == 1
    test = tests[0]
    assert isinstance(test, StatementCheckingTest)


def test_run_tests_from_s3():
    path_results = run_tests_from_s3('test', 'simple_model_test.pkl')

if __name__ == '__main__':
    #test_run_tests_from_s3()
    test_load_tests_from_s3()
