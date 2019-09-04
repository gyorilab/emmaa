import os
import json
from nose.plugins.attrib import attr
from emmaa.analyze_tests_results import TestRound, StatsGenerator


TestRound.__test__ = False


path_here = os.path.abspath(os.path.dirname(__file__))
previous_results_file = os.path.join(path_here, 'previous_results.json')
new_results_file = os.path.join(path_here, 'new_results.json')
previous_stats_file = os.path.join(path_here, 'previous_stats.json')
with open(previous_results_file, 'r') as f:
    previous_results = json.load(f)
with open(new_results_file, 'r') as f:
    new_results = json.load(f)
with open(previous_stats_file, 'r') as f:
    previous_stats = json.load(f)


@attr('nonpublic')
def test_test_round():
    tr = TestRound(previous_results)
    assert tr
    assert tr.get_total_statements() == 2
    assert len(tr.get_stmt_hashes()) == 2
    assert tr.get_statement_types() == [('Activation', 2)]
    assert all(agent_tuple in tr.get_agent_distribution() for agent_tuple in
               [('BRAF', 1), ('MAP2K1', 2), ('MAPK1', 1)])
    assert all((stmt_hash, 1) in tr.get_statements_by_evidence() for stmt_hash
               in tr.get_stmt_hashes())
    assert tr.get_total_applied_tests() == 1
    assert tr.get_number_passed_tests() == 1
    assert tr.get_applied_test_hashes() == tr.get_passed_test_hashes()
    assert tr.passed_over_total() == 1.0
    tr2 = TestRound(new_results)
    assert tr2
    assert tr2.find_numeric_delta(tr, 'get_total_statements') == 2
    assert tr2.find_numeric_delta(tr, 'get_total_applied_tests') == 1
    assert tr2.find_numeric_delta(tr, 'get_number_passed_tests') == 1
    assert tr2.find_numeric_delta(tr, 'passed_over_total') == 0
    assert len(tr2.find_content_delta(tr, 'statements')['added']) == 2
    assert len(tr2.find_content_delta(tr, 'applied_tests', True)['added']) == 1
    assert len(tr2.find_content_delta(tr, 'passed_tests')['added']) == 1
    assert len(tr2.find_content_delta(tr, 'paths')['added']) == 1


@attr('nonpublic')
def test_stats_generator():
    latest_round = TestRound(new_results)
    previous_round = TestRound(previous_results)
    sg = StatsGenerator('test', latest_round=latest_round,
                        previous_round=previous_round,
                        previous_json_stats=previous_stats)
    sg.make_stats()
    assert sg.json_stats
    model_summary = sg.json_stats['model_summary']
    assert model_summary['number_of_statements'] == 4
    assert model_summary['stmts_type_distr'] == [('Activation', 4)]
    assert all(agent_tuple in model_summary['agent_distr'] for
               agent_tuple in [('AKT', 2), ('BRAF', 2), ('MAP2K1', 2),
                               ('MTOR', 1), ('MAPK1', 1)])
    assert len(model_summary['stmts_by_evidence']) == 4
    assert len(model_summary['english_stmts']) == 4
    test_round_summary = sg.json_stats['test_round_summary']
    assert test_round_summary['number_applied_tests'] == 2
    assert len(test_round_summary['tests_by_hash']) == 2
    assert test_round_summary['pysb']['number_passed_tests'] == 2
    assert test_round_summary['pysb']['passed_ratio'] == 1.0
    assert len(test_round_summary['pysb']['passed_tests']) == 2
    assert len(test_round_summary['pysb']['paths']) == 2
    model_delta = sg.json_stats['model_delta']
    assert model_delta['number_of_statements_delta'] == 2
    assert len(model_delta['statements_delta']['added']) == 2
    tests_delta = sg.json_stats['tests_delta']
    assert tests_delta['number_applied_tests_delta'] == 1
    assert tests_delta['pysb']['number_passed_tests_delta'] == 1
    assert tests_delta['pysb']['passed_ratio_delta'] == 0
    assert len(tests_delta['pysb']['applied_tests_delta']['added']) == 1
    assert len(tests_delta['pysb']['pass_fail_delta']['added']) == 1
    assert len(tests_delta['pysb']['new_paths']['added']) == 1
    changes = sg.json_stats['changes_over_time']
    assert changes['number_of_statements'] == [2, 4]
    assert changes['number_applied_tests'] == [1, 2]
    assert len(changes['dates']) == 2
    assert changes['pysb']['number_passed_tests'] == [1, 2]
    assert changes['pysb']['passed_ratio'] == [1, 1]
