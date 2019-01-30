from emmaa.model_tests import (StatementCheckingTest, run_model_tests_from_s3,
                               load_tests_from_s3)

def test_load_tests_from_s3():
    tests = load_tests_from_s3('simple_model_test.pkl')
    assert isinstance(tests, list)
    assert len(tests) == 1
    test = tests[0]
    assert isinstance(test, StatementCheckingTest)


def test_run_tests_from_s3():
    tm = run_model_tests_from_s3('test', 'simple_model_test.pkl',
                                      upload_results=False)
    
    globals().update(locals())

if __name__ == '__main__':
    test_run_tests_from_s3()
