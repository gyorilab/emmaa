import json
import logging
from collections import defaultdict
from emmaa.util import find_latest_s3_file, get_s3_client


logger = logging.getLogger(__name__)


def load_latest_test_results_from_s3(model_name):
    base_key = f'results/{model_name}'
    latest_result_key = find_latest_s3_file('emmaa', f'{base_key}/results_',
                                            extension='.json')
    client = get_s3_client()
    logger.info(f'Loading test results from {latest_result_key}')
    obj = client.get_object(Bucket='emmaa', Key=latest_result_key)
    test_results = json.loads(obj['Body'].read().decode('utf8'))
    return test_results


def show_statistics(model_name):
    try:
        test_results = load_latest_test_results_from_s3(model_name)
    except IndexError:
        print('No test results for ' + model_name + ' model available.')
    else:
        total_tests = len(test_results)
        path_count = 0
        result_codes = defaultdict(int)
        for res in test_results:
            if res['result_json']['path_found']:
                path_count += 1
            else:
                result_codes[res['result_json']['result_code']] += 1
        return {'Model name': model_name, 'Total applied tests': total_tests,
                'Passed tests': path_count, 'Failed tests':
                [(key, value) for key, value in result_codes.items()]}

if __name__ == '__main__':
    cancer_types = ('aml', 'brca', 'luad', 'paad', 'prad', 'skcm')

    for ctype in cancer_types:
        print(show_statistics(ctype))