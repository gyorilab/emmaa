"""This module implements the object model for EMMAA model testing."""
import logging
import itertools
import jsonpickle
import os
import pickle
import sys
from collections import defaultdict
from fnvhash import fnv1a_32
from urllib import parse
from copy import deepcopy
from zipfile import ZipFile
from indra.explanation.model_checker import PysbModelChecker, \
    PybelModelChecker, SignedGraphModelChecker, UnsignedGraphModelChecker
from indra.explanation.reporting import stmts_from_pysb_path, \
    stmts_from_pybel_path, stmts_from_indranet_path, PybelEdge, \
    pybel_edge_to_english, RefEdge
from indra.explanation.pathfinding import bfs_search_multiple_nodes
from indra.assemblers.english.assembler import EnglishAssembler
from indra.sources.indra_db_rest.api import get_statement_queries
from indra.statements import Statement, Agent, Concept, Event, \
    stmts_to_json
from indra.util.statement_presentation import group_and_sort_statements, \
    make_string_from_relation_key
from indra.ontology.bio import bio_ontology
from bioagents.tra.tra import TRA, MissingMonomerError, MissingMonomerSiteError
from emmaa.model import EmmaaModel, get_assembled_statements, \
    load_config_from_s3
from emmaa.queries import PathProperty, DynamicProperty, OpenSearchQuery
from emmaa.util import make_date_str, get_s3_client, get_class_from_name, \
    EMMAA_BUCKET_NAME, find_latest_s3_file, load_pickle_from_s3, \
    save_pickle_to_s3, load_json_from_s3, save_json_to_s3, strip_out_date, \
    save_gzip_json_to_s3
from emmaa.filter_functions import filter_functions


logger = logging.getLogger(__name__)
sys.setrecursionlimit(50000)


result_codes_link = ('https://emmaa.readthedocs.io/en/latest/dashboard/'
                     'response_codes.html')
RESULT_CODES = {
    'STATEMENT_TYPE_NOT_HANDLED': 'Statement type not handled',
    'SUBJECT_MONOMERS_NOT_FOUND': 'Statement subject not in model',
    'SUBJECT_NOT_FOUND': 'Statement subject not in model',
    'OBSERVABLES_NOT_FOUND': 'Statement object state not in model',
    'OBJECT_NOT_FOUND': 'Statement object state not in model',
    'NO_PATHS_FOUND': 'No path found that satisfies the test statement',
    'MAX_PATH_LENGTH_EXCEEDED': 'Path found but exceeds search depth',
    'PATHS_FOUND': 'Path found which satisfies the test statement',
    'INPUT_RULES_NOT_FOUND': 'No rules with test statement subject',
    'MAX_PATHS_ZERO': 'Path found but not reconstructed',
    'QUERY_NOT_APPLICABLE': 'Query is not applicable for this model',
    'NODE_NOT_FOUND': 'Node not in model'
}
ARROW_DICT = {'Complex': u"\u2194",
              'Inhibition': u"\u22A3",
              'DecreaseAmount': u"\u22A3"}


class ModelManager(object):
    """Manager to generate and store properties of a model and relevant tests.

    Parameters
    ----------
    model : emmaa.model.EmmaaModel
        EMMAA model

    Attributes
    ----------
    mc_mapping : dict
        A dictionary mapping a ModelChecker type to a corresponding method
        for assembling the model and a ModelChecker class.
    mc_types : dict
        A dictionary in which each key is a type of a ModelChecker and value is
        a dictionary containing an instance of a model, an instance of a
        ModelChecker and a list of test results.
    entities : list[indra.statements.agent.Agent]
        A list of entities of EMMAA model.
    applicable_tests : list[emmaa.model_tests.EmmaaTest]
        A list of EMMAA tests applicable for given EMMAA model.
    date_str : str
        Time when this object was created.
    """
    def __init__(self, model, mode='local'):
        self.model = model
        self.mc_mapping = {
            'pysb': (self.model.assemble_pysb, PysbModelChecker,
                     stmts_from_pysb_path),
            'pybel': (self.model.assemble_pybel, PybelModelChecker,
                      stmts_from_pybel_path),
            'signed_graph': (self.model.assemble_signed_graph,
                             SignedGraphModelChecker,
                             stmts_from_indranet_path),
            'unsigned_graph': (self.model.assemble_unsigned_graph,
                               UnsignedGraphModelChecker,
                               stmts_from_indranet_path)}
        self.mc_types = {}
        for mc_type in model.test_config.get('mc_types', ['pysb']):
            self.mc_types[mc_type] = {}
            assembled_model = self.mc_mapping[mc_type][0](mode=mode)
            self.mc_types[mc_type]['model'] = assembled_model
            self.mc_types[mc_type]['model_checker'] = (
                self.mc_mapping[mc_type][1](assembled_model))
            self.mc_types[mc_type]['test_results'] = []
        self.entities = self.model.get_assembled_entities()
        self.applicable_tests = []
        self.date_str = self.model.date_str
        self.path_stmt_counts = defaultdict(int)

    @classmethod
    def load_from_statements(cls, model_name, mode='local', date=None,
                             bucket=EMMAA_BUCKET_NAME):
        config = load_config_from_s3(model_name, bucket=bucket)
        if date:
            prefix = f'papers/{model_name}/paper_ids_{date}'
        else:
            prefix = f'papers/{model_name}/paper_ids_'
        paper_key = find_latest_s3_file(bucket, prefix, 'json')
        if paper_key:
            paper_ids = load_json_from_s3(bucket, paper_key)
        else:
            paper_ids = None
        model = EmmaaModel(model_name, config, paper_ids)
        # Loading assembled statements to avoid reassembly
        stmts, fname = get_assembled_statements(model_name, date, bucket)
        model.assembled_stmts = stmts
        model.date_str = strip_out_date(fname, 'datetime')
        mm = cls(model, mode=mode)
        return mm

    def get_updated_mc(self, mc_type, stmts, add_ns=False):
        """Update the ModelChecker and graph with stmts for tests/queries."""
        mc = self.mc_types[mc_type]['model_checker']
        mc.statements = stmts
        if mc_type == 'pysb':
            mc.graph = None
            mc.model_stmts = self.model.assembled_stmts
            mc.get_graph(prune_im=True, prune_im_degrade=True,
                         add_namespaces=add_ns)
        if mc_type in ('signed_graph', 'unsigned_graph'):
            mc.nodes_to_agents = {ag.name: ag for ag in self.entities}
        return mc

    def add_test(self, test):
        """Add a test to a list of applicable tests."""
        self.applicable_tests.append(test)

    def add_result(self, mc_type, result):
        """Add a result to a list of results."""
        self.mc_types[mc_type]['test_results'].append(result)

    def run_all_tests(self, filter_func=None):
        """Run all applicable tests with all available ModelCheckers."""
        max_path_length, max_paths = self._get_test_configs()
        for mc_type in self.mc_types:
            self.run_tests_per_mc(mc_type, max_path_length, max_paths,
                                  filter_func)

    def run_tests_per_mc(self, mc_type, max_path_length, max_paths,
                         filter_func=None):
        """Run all applicable tests with one ModelChecker."""
        mc = self.get_updated_mc(
            mc_type, [test.stmt for test in self.applicable_tests])
        logger.info(f'Running the tests with {mc_type} ModelChecker.')
        if filter_func:
            logger.info(f'Applying {filter_func.__name__}')
        results = mc.check_model(
            max_path_length=max_path_length, max_paths=max_paths,
            agent_filter_func=filter_func)
        for (stmt, result) in results:
            self.add_result(mc_type, result)

    def make_path_json(self, mc_type, result_paths):
        paths = []
        json_lines = []
        for path in result_paths:
            path_nodes = []
            edge_list = []
            path_node_list = []
            hashes = []
            report_function = self.mc_mapping[mc_type][2]
            model = self.mc_types[mc_type]['model']
            stmts = self.model.assembled_stmts
            if mc_type == 'pysb':
                report_stmts = report_function(path, model, stmts)
                path_stmts = [[st] for st in report_stmts]
                merge = False
            elif mc_type == 'pybel':
                path_stmts = report_function(path, model, False, stmts)
                merge = False
            elif mc_type == 'signed_graph':
                path_stmts = report_function(path, model, True, False, stmts)
                merge = True
            elif mc_type == 'unsigned_graph':
                path_stmts = report_function(path, model, False, False, stmts)
                merge = True
            for i, step in enumerate(path_stmts):
                edge_nodes = []
                if len(step) < 1:
                    continue
                stmt_type = type(step[0]).__name__
                if stmt_type in ('PybelEdge', 'RefEdge'):
                    source, target = step[0].source, step[0].target
                    edge_nodes.append(source.name)
                    edge_nodes.append(u"\u2192")
                    edge_nodes.append(target.name)
                    hashes.append({'type': stmt_type})
                else:
                    step_hashes = []
                    for stmt in step:
                        self.path_stmt_counts[stmt.get_hash()] += 1
                        step_hashes.append(stmt.get_hash())
                    hashes.append({'type': 'statements',
                                   'hashes': step_hashes})
                    agents = [ag.name if ag is not None else None
                              for ag in step[0].agent_list()]
                    # For complexes make sure that the agent from the
                    # previous edge goes first
                    if stmt_type == 'Complex' and len(path_nodes) > 0:
                        agents = sorted(
                            [ag for ag in agents if ag is not None],
                            key=lambda x: x != path_nodes[-1])
                    for j, ag in enumerate(agents):
                        if ag is not None:
                            edge_nodes.append(ag)
                        if j == (len(agents) - 1):
                            break
                        if stmt_type in ARROW_DICT:
                            edge_nodes.append(ARROW_DICT[stmt_type])
                        else:
                            edge_nodes.append(u"\u2192")
                if i == 0:
                    for n in edge_nodes:
                        path_nodes.append(n)
                    path_node_list.append(edge_nodes[0])
                    path_node_list.append(edge_nodes[-1])
                else:
                    for n in edge_nodes[1:]:
                        path_nodes.append(n)
                    path_node_list.append(edge_nodes[-1])
                step_sentences = self._make_path_stmts(step, merge=merge)
                edge_dict = {'edge': ' '.join(edge_nodes),
                             'stmts': step_sentences}
                edge_list.append(edge_dict)
            path_json = {'path': ' '.join(path_nodes),
                         'edge_list': edge_list}
            one_line_path_json = {'nodes': path_node_list, 'edges': hashes,
                                  'graph_type': mc_type}
            paths.append(path_json)
            json_lines.append(one_line_path_json)
        return paths, json_lines

    def _make_path_stmts(self, stmts, merge=False):
        sentences = []
        date = strip_out_date(self.date_str, 'date')
        if merge and isinstance(stmts[0], Statement):
            groups = group_and_sort_statements(stmts, grouping_level='relation')
            for _, rel_key, group_stmts, _ in groups:
                sentence = make_string_from_relation_key(rel_key) + '.'
                stmt_hashes = [gr_st.get_hash()
                               for _, _, gr_st, _ in group_stmts]
                url_param = parse.urlencode(
                    {'stmt_hash': stmt_hashes, 'source': 'model_statement',
                     'model': self.model.name, 'date': date}, doseq=True)
                link = f'/evidence?{url_param}'
                sentences.append((link, sentence, ''))
        else:
            for stmt in stmts:
                if isinstance(stmt, PybelEdge):
                    sentence = pybel_edge_to_english(stmt)
                    sentences.append(('', sentence, ''))
                elif isinstance(stmt, RefEdge):
                    sentence = stmt.to_english()
                    sentences.append(('', sentence, ''))
                else:
                    ea = EnglishAssembler([stmt])
                    sentence = ea.make_model()
                    stmt_hashes = [stmt.get_hash()]
                    url_param = parse.urlencode(
                        {'stmt_hash': stmt_hashes, 'source': 'model_statement',
                         'model': self.model.name, 'date': date}, doseq=True)
                    link = f'/evidence?{url_param}'
                    sentences.append((link, sentence, ''))
        return sentences

    def make_result_code(self, result):
        result_code = result.result_code
        return RESULT_CODES[result_code]

    def answer_query(self, query, **kwargs):
        if isinstance(query, DynamicProperty):
            return self.answer_dynamic_query(query, **kwargs)
        if isinstance(query, PathProperty):
            return self.answer_path_query(query)
        if isinstance(query, OpenSearchQuery):
            return self.answer_open_query(query)

    def answer_path_query(self, query):
        """Answer user query with a path if it is found."""
        if ScopeTestConnector.applicable(self, query):
            results = []
            for mc_type in self.mc_types:
                mc = self.get_updated_mc(mc_type, [query.path_stmt])
                max_path_length, max_paths = self._get_test_configs(
                    mode='query', mc_type=mc_type, default_paths=5)
                result = mc.check_statement(
                    query.path_stmt, max_paths, max_path_length)
                hashed_res, path_lines = self.process_response(mc_type, result)
                results.append((mc_type, hashed_res, path_lines))
            return results
        else:
            return [('', self.hash_response_list(
                RESULT_CODES['QUERY_NOT_APPLICABLE']),
                     RESULT_CODES['QUERY_NOT_APPLICABLE'])]

    def answer_dynamic_query(self, query, use_kappa=False,
                             bucket=EMMAA_BUCKET_NAME):
        """Answer user query by simulating a PySB model."""
        tra = TRA(use_kappa=use_kappa)
        tp = query.get_temporal_pattern()
        pysb_model = deepcopy(self.mc_types['pysb']['model'])
        try:
            sat_rate, num_sim, kpat, pat_obj, fig_path = tra.check_property(
                pysb_model, tp)
            fig_name, ext = os.path.splitext(os.path.basename(fig_path))
            date_str = make_date_str()
            s3_key = (f'query_images/{self.model.name}/{fig_name}_'
                      f'{date_str}{ext}')
            s3_path = f'https://{bucket}.s3.amazonaws.com/{s3_key}'
            client = get_s3_client(unsigned=False)
            logger.info(f'Uploading image to {s3_path}')
            client.upload_file(fig_path, Bucket=bucket, Key=s3_key)
            resp_json = {'sat_rate': sat_rate, 'num_sim': num_sim,
                         'kpat': kpat, 'fig_path': s3_path}
        except (MissingMonomerError, MissingMonomerSiteError):
            resp_json = RESULT_CODES['QUERY_NOT_APPLICABLE']
        return [('pysb', self.hash_response_list(resp_json), resp_json)]

    def answer_open_query(self, query):
        """Answer user open search query with found paths."""
        if ScopeTestConnector.applicable(self, query):
            results = []
            for mc_type in self.mc_types:
                max_path_length, max_paths = self._get_test_configs(
                    mode='query', qtype='open_search', mc_type=mc_type,
                    default_paths=50, default_length=2)
                add_ns = False
                if query.terminal_ns:
                    add_ns = True
                mc = self.get_updated_mc(mc_type, [query.path_stmt], add_ns)
                res, paths = self.open_query_per_mc(
                    mc_type, mc, query, max_path_length, max_paths)
                results.append((mc_type, res, paths))
            return results
        else:
            return [('', self.hash_response_list(
                RESULT_CODES['QUERY_NOT_APPLICABLE']),
                     RESULT_CODES['QUERY_NOT_APPLICABLE'])]

    def open_query_per_mc(self, mc_type, mc, query, max_path_length,
                          max_paths):
        g = mc.get_graph()
        subj_nodes, obj_nodes, res_code = mc.process_statement(query.path_stmt)
        if res_code:
            return self.hash_response_list(RESULT_CODES[res_code])
        else:
            if query.entity_role == 'subject':
                reverse = False
                assert subj_nodes.all_nodes
                nodes = subj_nodes.all_nodes
            else:
                reverse = True
                assert obj_nodes
                nodes = obj_nodes.all_nodes
            sign = query.get_sign(mc_type)
            if mc_type == 'pysb':
                terminal_ns = None
            else:
                terminal_ns = query.terminal_ns
            paths_gen = bfs_search_multiple_nodes(
                g, nodes, reverse=reverse, terminal_ns=terminal_ns,
                depth_limit=max_path_length, path_limit=max_paths, sign=sign)
            paths = []
            for p in paths_gen:
                if reverse:
                    paths.append(p[::-1])
                else:
                    paths.append(p)
            return self.process_open_query_response(mc_type, paths)

    def answer_queries(self, queries, **kwargs):
        """Answer all queries registered for this model.

        Parameters
        ----------
        queries : list[emmaa.queries.Query]
            A list of queries to run.

        Returns
        -------
        responses : list[tuple(json, json)]
            A list of tuples each containing a query, mc_type and result json.
        """
        responses = []
        applicable_queries = []
        applicable_stmts = []
        applicable_open_queries = []
        applicable_open_stmts = []
        for query in queries:
            # Dynamic queries need to be answered individually, while for
            # path and open queries some parts can be shared
            if isinstance(query, DynamicProperty):
                mc_type, response, resp_json = self.answer_dynamic_query(
                    query, **kwargs)[0]
                responses.append((query, mc_type, response))
            elif isinstance(query, PathProperty):
                if ScopeTestConnector.applicable(self, query):
                    applicable_queries.append(query)
                    applicable_stmts.append(query.path_stmt)
                else:
                    responses.append(
                        (query, '', self.hash_response_list(
                            RESULT_CODES['QUERY_NOT_APPLICABLE'])))
            elif isinstance(query, OpenSearchQuery):
                if ScopeTestConnector.applicable(self, query):
                    applicable_open_queries.append(query)
                    applicable_open_stmts.append(query.path_stmt)
                else:
                    responses.append(
                        (query, '', self.hash_response_list(
                            RESULT_CODES['QUERY_NOT_APPLICABLE'])))

        # Only do the following steps if there are applicable queries
        # Path queries
        if applicable_queries:
            for mc_type in self.mc_types:
                mc = self.get_updated_mc(mc_type, applicable_stmts)
                max_path_length, max_paths = self._get_test_configs(
                    mode='query', mc_type=mc_type, default_paths=5)
                results = mc.check_model(
                    max_path_length=max_path_length, max_paths=max_paths)
                for ix, (_, result) in enumerate(results):
                    resp, paths = self.process_response(mc_type, result)
                    responses.append(
                        (applicable_queries[ix], mc_type, resp))

        # Open queries
        if applicable_open_queries:
            for mc_type in self.mc_types:
                max_path_length, max_paths = self._get_test_configs(
                    mode='query', mc_type=mc_type, default_paths=50,
                    default_length=2)
                mc = self.get_updated_mc(mc_type, applicable_open_stmts, True)
                for query in applicable_open_queries:
                    res, paths = self.open_query_per_mc(
                        mc_type, mc, query, max_path_length, max_paths)
                    responses.append((query, mc_type, res))

        return sorted(responses, key=lambda x: x[0].matches_key())

    def _get_test_configs(self, mode='test', qtype='statement_checking',
                          mc_type=None, default_length=5, default_paths=1):
        if mode == 'test':
            config = self.model.test_config
        elif mode == 'query':
            config = self.model.query_config
        try:
            max_path_length = \
                config[qtype][mc_type]['max_path_length']
        except KeyError:
            try:
                max_path_length = \
                    config[qtype]['max_path_length']
            except KeyError:
                max_path_length = default_length
        try:
            max_paths = \
                config[qtype][mc_type]['max_paths']
        except KeyError:
            try:
                max_paths = \
                    config[qtype]['max_paths']
            except KeyError:
                max_paths = default_paths
        logger.info('Parameters for model checking: %d, %d' %
                    (max_path_length, max_paths))
        return (max_path_length, max_paths)

    def process_response(self, mc_type, result):
        """Return a dictionary in which every key is a hash and value is a list
        of tuples. Each tuple contains a sentence describing either a step in a
        path (if it was found) or result code (if a path was not found) and a
        link leading to a webpage with more information about corresponding
        sentence.
        """
        if result.paths:
            response, path_lines = self.make_path_json(mc_type, result.paths)
            return self.hash_response_list(response), path_lines
        else:
            response = self.make_result_code(result)
            return self.hash_response_list(response), response

    def process_open_query_response(self, mc_type, paths):
        if paths:
            response, path_lines = self.make_path_json(mc_type, paths)
            return self.hash_response_list(response), path_lines
        else:
            response = 'No paths found that satisfy this query'
            return self.hash_response_list(response), response

    def hash_response_list(self, response):
        """Return a dictionary mapping a hash with a response in a response
        list.
        """
        response_dict = {}
        if isinstance(response, str):
            response_hash = str(fnv1a_32(response.encode('utf-8')))
            response_dict[response_hash] = response
        elif isinstance(response, list):
            for resp in response:
                sentences = []
                for edge in resp['edge_list']:
                    for (_, sentence, _) in edge['stmts']:
                        sentences.append(sentence)
                response_str = ' '.join(sentences)
                response_hash = str(fnv1a_32(response_str.encode('utf-8')))
                response_dict[response_hash] = resp
        elif isinstance(response, dict):
            results = [str(response.get('sat_rate')),
                       str(response.get('num_sim'))]
            response_str = ' '.join(results)
            response_hash = str(fnv1a_32(response_str.encode('utf-8')))
            response_dict[response_hash] = response
        else:
            raise TypeError('Response should be a string or a list.')
        return response_dict

    def results_to_json(self, test_data=None):
        """Put test results to json format."""
        pickler = jsonpickle.pickler.Pickler()
        results_json = []
        results_json.append({
            'model_name': self.model.name,
            'mc_types': [mc_type for mc_type in self.mc_types.keys()],
            'path_stmt_counts': self.path_stmt_counts,
            'date_str': self.date_str,
            'test_data': test_data})
        json_lines = []
        for ix, test in enumerate(self.applicable_tests):
            test_ix_results = {'test_type': test.__class__.__name__,
                               'test_json': test.to_json()}
            for mc_type in self.mc_types:
                result = self.mc_types[mc_type]['test_results'][ix]
                path_json, test_json_lines = self.make_path_json(
                    mc_type, result.paths)
                test_ix_results[mc_type] = {
                    'result_json': pickler.flatten(result),
                    'path_json': path_json,
                    'result_code': self.make_result_code(result)}
                for line in test_json_lines:
                    # Only include lines with paths
                    if line:
                        line.update({'test': test.stmt.get_hash()})
                        json_lines.append(line)
            results_json.append(test_ix_results)
        return results_json, json_lines

    def upload_results(self, test_corpus='large_corpus_tests',
                       test_data=None, bucket=EMMAA_BUCKET_NAME):
        """Upload results to s3 bucket."""
        json_dict, json_lines = self.results_to_json(test_data)
        result_key = (f'results/{self.model.name}/results_'
                      f'{test_corpus}_{self.date_str}.json')
        paths_key = (f'paths/{self.model.name}/paths_{test_corpus}_'
                     f'{self.date_str}.jsonl')
        latest_paths_key = (f'paths/{self.model.name}/{test_corpus}'
                            '_latest_paths.jsonl')
        logger.info(f'Uploading test results to {result_key}')
        save_json_to_s3(json_dict, bucket, result_key)
        logger.info(f'Uploading test paths to {paths_key}')
        save_json_to_s3(json_lines, bucket, paths_key, save_format='jsonl')
        save_json_to_s3(json_lines, bucket, latest_paths_key, 'jsonl')

    def save_assembled_statements(self, bucket=EMMAA_BUCKET_NAME):
        """Upload assembled statements jsons to S3 bucket."""
        stmts = self.model.assembled_stmts
        stmts_json = stmts_to_json(stmts)
        # Save a timestapmed version and a generic latest version of files
        dated_key = f'assembled/{self.model.name}/statements_{self.date_str}'
        latest_key = f'assembled/{self.model.name}/' \
                     f'latest_statements_{self.model.name}'
        for ext in ('json', 'jsonl'):
            latest_obj_key = latest_key + '.' + ext
            logger.info(f'Uploading assembled statements to {latest_obj_key}')
            save_json_to_s3(stmts_json, bucket, latest_obj_key, ext)
        dated_jsonl = dated_key + '.jsonl'
        dated_zip = dated_key + '.gz'
        logger.info(f'Uploading assembled statements to {dated_jsonl}')
        save_json_to_s3(stmts_json, bucket, dated_jsonl, 'jsonl')
        logger.info(f'Uploading assembled statements to {dated_zip}')
        save_gzip_json_to_s3(stmts_json, bucket, dated_zip, 'json')


class TestManager(object):
    """Manager to generate and run a set of tests on a set of models.

    Parameters
    ----------
    model_managers : list[emmaa.model_tests.ModelManager]
        A list of ModelManager objects
    tests : list[emmaa.model_tests.EmmaaTest]
        A list of EMMAA tests
    """
    def __init__(self, model_managers, tests):
        self.model_managers = model_managers
        self.tests = tests

    def make_tests(self, test_connector):
        """Generate a list of applicable tests for each model with a given test
        connector.

        Parameters
        ----------
        test_connector : emmaa.model_tests.TestConnector
            A TestConnector object to use for connecting models to tests.
        """
        logger.info(f'Checking applicability of {len(self.tests)} tests to '
                    f'{len(self.model_managers)} models')
        for model_manager, test in itertools.product(self.model_managers,
                                                     self.tests):
            if test_connector.applicable(model_manager, test):
                model_manager.add_test(test)
                logger.debug(f'Test {test.stmt} is applicable')
            else:
                logger.debug(f'Test {test.stmt} is not applicable')
        logger.info(f'Created tests for {len(self.model_managers)} models.')
        for model_manager in self.model_managers:
            logger.info(f'Created {len(model_manager.applicable_tests)} tests '
                        f'for {model_manager.model.name} model.')

    def run_tests(self, filter_func=None):
        """Run tests for a list of model-test pairs"""
        for model_manager in self.model_managers:
            model_manager.run_all_tests(filter_func)


class TestConnector(object):
    """Determines if a given test is applicable to a given model."""
    def __init__(self):
        pass

    @staticmethod
    def applicable(model, test):
        """Return True if the test is applicable to the given model."""
        return True


class ScopeTestConnector(TestConnector):
    """Determines applicability of a test to a model by overlap in scope."""
    @staticmethod
    def applicable(model, test):
        """Return True of all test entities are in the set of model entities"""
        model_entities = model.entities
        test_entities = test.get_entities()
        return ScopeTestConnector._overlap(model_entities, test_entities)

    @staticmethod
    def _overlap(model_entities, test_entities):
        me_names = {e.name for e in model_entities}
        te_names = {e.name for e in test_entities}
        # If all test entities are in model entities, we get an empty set here
        # so we return True
        return not te_names - me_names


class RefinementTestConnector(TestConnector):
    """Determines applicability of a test to a model by checking if test
    entities or their refinements are in the model.
    """
    @staticmethod
    def applicable(model, test):
        """Return True of all test entities are in the set of model entities"""
        model_entities = model.entities
        test_entities = test.get_entities()
        test_entity_groups = []
        for te in test_entities:
            te_group = [te]
            ns, gr = te.get_grounding()
            children = bio_ontology.get_children(ns, gr)
            for ns, gr in children:
                name = bio_ontology.get_name(ns, gr)
                ag = Agent(name, db_refs={ns: gr})
                te_group.append(ag)
            test_entity_groups.append(te_group)
        return RefinementTestConnector._overlap(model_entities,
                                                test_entity_groups)

    @staticmethod
    def _ref_group_overlap(model_entities, test_entity_group):
        me_names = {e.name for e in model_entities}
        te_names = {e.name for e in test_entity_group}
        # We need at least one intersection between these groups
        return me_names.intersection(te_names)

    @staticmethod
    def _overlap(model_entities, test_entity_groups):
        # We need to get overlap with each test entity group
        return all([RefinementTestConnector._ref_group_overlap(
            model_entities, te_group) for te_group in test_entity_groups])


class EmmaaTest(object):
    """Represent an EMMAA test condition"""
    def get_entities(self):
        """Return a list of entities that the test checks for."""
        raise NotImplementedError()


class StatementCheckingTest(EmmaaTest):
    """Represent an EMMAA test condition that checks a PySB-assembled model
    against an INDRA Statement."""
    def __init__(self, stmt, configs=None):
        self.stmt = stmt
        self.configs = {} if not configs else configs
        logger.info('Test configs: %s' % configs)
        # TODO
        # Add entities as a property if we can reload tests on s3.
        # self.entities = self.get_entities()

    def check(self, model_checker, pysb_model):
        """Use a model checker to check if a given model satisfies the test."""
        max_path_length = self.configs.get('max_path_length', 5)
        max_paths = self.configs.get('max_paths', 1)
        logger.info('Parameters for model checking: %s, %d' %
                    (max_path_length, max_paths))
        res = model_checker.check_statement(
            self.stmt,
            max_path_length=max_path_length,
            max_paths=max_paths)
        return res

    def get_entities(self):
        """Return a list of entities that the test checks for."""
        return self.stmt.agent_list()

    def to_json(self):
        return self.stmt.to_json()

    def __repr__(self):
        return "%s(stmt=%s)" % (self.__class__.__name__, repr(self.stmt))


def load_tests_from_s3(test_name, bucket=EMMAA_BUCKET_NAME):
    """Load Emmaa Tests with the given name from S3.

    Parameters
    ----------
    test_name : str
        Looks for a test file in the emmaa bucket on S3 with key
        'tests/{test_name}'.

    Return
    ------
    list of EmmaaTest
        List of EmmaaTest objects loaded from S3.
    """
    prefix = f'tests/{test_name}'
    try:
        test_key = find_latest_s3_file(bucket, prefix, '.pkl')
    except ValueError:
        test_key = f'tests/{test_name}.pkl'
    logger.info(f'Loading tests from {test_key}')
    tests = load_pickle_from_s3(bucket, test_key)
    return tests, test_key


def save_model_manager_to_s3(model_name, model_manager,
                             bucket=EMMAA_BUCKET_NAME):
    logger.info(f'Saving a model manager for {model_name} model to S3.')
    date_str = model_manager.date_str
    model_manager.model.stmts = []
    model_manager.model.assembled_stmts = []
    save_pickle_to_s3(model_manager, bucket,
                      f'results/{model_name}/model_manager_{date_str}.pkl')


def load_model_manager_from_s3(model_name=None, key=None,
                               bucket=EMMAA_BUCKET_NAME):
    # First try find the file from specified key
    if key:
        try:
            model_manager = load_pickle_from_s3(bucket, key)
            if not model_manager.model.assembled_stmts:
                stmts, _ = get_assembled_statements(
                    model_manager.model.name,
                    strip_out_date(model_manager.date_str, 'date'),
                    bucket=bucket)
                model_manager.model.assembled_stmts = stmts
            return model_manager
        except Exception as e:
            logger.info('Could not load the model manager directly')
            logger.info(e)
            if not model_name:
                model_name = key.split('/')[1]
            date = strip_out_date(key, 'date')
            logger.info('Trying to load model manager from statements')
            try:
                model_manager = ModelManager.load_from_statements(
                    model_name, date=date, bucket=bucket)
                return model_manager
            except Exception as e:
                logger.info('Could not load the model manager from '
                            'statements')
                logger.info(e)
                return None
    # Now try find the latest key for given model
    if model_name:
        # Versioned
        key = find_latest_s3_file(
            bucket, f'results/{model_name}/model_manager_', '.pkl')
        if key is None:
            # Non-versioned
            key = f'results/{model_name}/latest_model_manager.pkl'
        return load_model_manager_from_s3(model_name=model_name, key=key,
                                          bucket=bucket)
    # Could not find either from key or from model name.
    logger.info('Could not find the model manager.')
    return None


def update_model_manager_on_s3(model_name, bucket=EMMAA_BUCKET_NAME):
    model = EmmaaModel.load_from_s3(model_name, bucket=bucket)
    mm = ModelManager(model)
    save_model_manager_to_s3(model_name, mm, bucket=bucket)
    return mm


def model_to_tests(model_name, upload=True, bucket=EMMAA_BUCKET_NAME):
    em = EmmaaModel.load_from_s3(model_name, bucket=bucket)
    em.run_assembly()
    tests = [StatementCheckingTest(stmt) for stmt in em.assembled_stmts if
             all(stmt.agent_list())]
    date_str = make_date_str()
    test_description = (
        f'These tests were generated from the {em.human_readable_name} '
        f'on {date_str[:10]}')
    test_name = f'{em.human_readable_name} model test corpus'
    test_dict = {'test_data': {'description': test_description,
                               'name': test_name},
                 'tests': tests}
    if upload:
        save_tests_to_s3(test_dict, bucket,
                         f'tests/{model_name}_tests_{date_str}.pkl', 'pkl')
    return test_dict


def save_tests_to_s3(tests, bucket, key, save_format='pkl'):
    """Save tests in pkl, json or jsonl format."""
    if save_format == 'pkl':
        save_pickle_to_s3(tests, bucket, key)
    elif save_format in ['json', 'jsonl']:
        if isinstance(tests, list):
            stmts = [test.stmt for test in tests]
        elif isinstance(tests, dict):
            stmts = [test.stmt for test in tests['tests']]
        stmts_json = stmts_to_json(stmts)
        save_json_to_s3(stmts_json, bucket, key, save_format)


def run_model_tests_from_s3(model_name, test_corpus='large_corpus_tests',
                            upload_results=True, bucket=EMMAA_BUCKET_NAME):
    """Run a given set of tests on a given model, both loaded from S3.

    After loading both the model and the set of tests, model/test overlap
    is determined using a ScopeTestConnector and tests are run.


    Parameters
    ----------
    model_name : str
        Name of EmmaaModel to load from S3.
    test_corpus : str
        Name of the file containing tests on S3.
    upload_results : Optional[bool]
        Whether to upload test results to S3 in JSON format. Can be set
        to False when running tests. Default: True

    Returns
    -------
    emmaa.model_tests.ModelManager
        Instance of ModelManager containing the model data, list of applied
        tests and the test results.
    """
    mm = load_model_manager_from_s3(model_name=model_name, bucket=bucket)
    test_dict, _ = load_tests_from_s3(test_corpus, bucket=bucket)
    if isinstance(test_dict, dict):
        tests = test_dict['tests']
        test_data = test_dict['test_data']
    elif isinstance(test_dict, list):
        tests = test_dict
        test_data = None
    tm = TestManager([mm], tests)
    tc = mm.model.test_config.get('test_connector', 'refinement')
    if tc == 'scope':
        test_connector = ScopeTestConnector()
    elif tc == 'refinement':
        test_connector = RefinementTestConnector()
    tm.make_tests(test_connector)
    filter_func = None
    if mm.model.test_config.get('filters'):
        filter_func_name = mm.model.test_config['filters'].get(test_corpus)
        if filter_func_name:
            filter_func = filter_functions.get(filter_func_name)
    tm.run_tests(filter_func)
    # Optionally upload test results to S3
    if upload_results:
        mm.upload_results(test_corpus, test_data, bucket=bucket)
    return mm
