from emmaa.priors import SearchTerm
from emmaa.model import save_config_to_s3
from emmaa.model_tests import StatementCheckingTest
from indra.sources.eidos import process_text
from indra.tools.assemble_corpus import standardize_names_groundings


def make_search_terms(terms, ontology_file, db_ns):
    """Make SearchTerm objects standardized to a given ontology from terms.

    Parameters
    ----------
    terms : list[str]
        A list of terms corresponding to suffixes of entries in the ontology.
    ontology_file : str
        A path to a file containing ontology.

    Returns
    -------
    search_terms : set
        A set of SearchTerm objects constructed from given terms and ontology
        having standardized names.
    """
    search_terms = set()
    search_names = set()
    with open(ontology_file, 'r') as f:
        lines = f.readlines()
    ontologies = []
    for line in lines:
        links = line.split('> <')
        link = links[0]
        ont_start = link.find(db_ns)
        ont = link[ont_start:]
        ontologies.append(ont)
    for ont in ontologies:
        for term in terms:
            if term in ont:
                search_term = ont.split('/')[-1]
                search_term = search_term.replace('_', ' ')
                name = search_term.capitalize()
                st = SearchTerm(type='concept', name=name,
                                db_refs={db_ns.upper(): ont},
                                search_term='\"%s\"' % search_term)
                if name not in search_names:
                    search_terms.add(st)
                    search_names.add(name)
    return search_terms


def make_config(search_terms, human_readable_name, description,
                short_name, ndex_network=None, save_to_s3=False):
    """Make a config file for WorldModelers models and optionally save to S3."""
    config = {}
    config['ndex'] = {'network': ndex_network if ndex_network else ''}
    config['human_readable_name'] = human_readable_name
    config['search_terms'] = [st.to_json() for st in search_terms]
    config['test'] = {'statement_checking': {
                      'max_path_length': 5,
                      'max_paths': 1},
                      'test_corpus': 'world_modelers_tests.pkl',
                      'mc_types': ['pysb', 'signed_graph', 'unsigned_graph'],
                      'make_links': False,
                      'link_type': 'elsevier'}
    config['assembly'] = {'skip_map_grounding': True,
                          'skip_filter_human': True,
                          'skip_map_sequence': True,
                          'belief_cutoff': 0.8,
                          'filter_ungrounded': True,
                          'score_threshold': 0.7,
                          'filter_relevance': 'prior_one',
                          'standardize_names': True,
                          'preassembly_mode': 'wm'}
    config['reading'] = {'literature_source': 'elsevier',
                         'reader': 'elsevier_eidos'}
    config['description'] = description
    config['run_daily_update'] = True
    if save_to_s3:
        save_config_to_s3(short_name, config)
    return config


def reground_tests(tests, webservice):
    """Reground tests to updated ontology."""
    stmts = [test.stmt for test in tests]
    texts = [stmt.evidence[0].text for stmt in stmts]
    text = ' '.join(texts)
    new_stmts = process_text(text, webservice=webservice).statements
    new_stmts = standardize_names_groundings(new_stmts)
    new_tests = [StatementCheckingTest(stmt) for stmt in new_stmts]
    return new_tests
