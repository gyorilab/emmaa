from emmaa.model_tests import run_tests_from_s3

def test_run_tests_from_s3():
    path_results = run_tests_from_s3('test', 'simple_model_test.pkl')

if __name__ == '__main__':
    test_run_tests_from_s3()

