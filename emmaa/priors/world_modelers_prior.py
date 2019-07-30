from emmaa.priors import SearchTerm
from emmaa.model import save_config_to_s3


def make_search_terms(terms, ontology_file):
    search_terms = set()
    with open(ontology_file, 'r') as f:
        lines = f.readlines()
    ontologies = []
    for line in lines:
        links = line.split('> <')
        link = links[0]
        ont_start = link.find('UN')
        ont = link[ont_start:]
        ontologies.append(ont)
    for ont in ontologies:
        for term in terms:
            if ont.endswith(term):
                search_term = term.replace('_', ' ')
                name = search_term.capitalize()
                st = SearchTerm(type='concept', name=name, db_refs={'UN': ont},
                                search_term='\"%s\"' % search_term)
                search_terms.add(st)
    return search_terms


def make_config(search_terms, human_readable_name, description,
                short_name, ndex_network=None, save_to_s3=False):
    config = {}
    if ndex_network:
        config['ndex'] = {'network': ndex_network}
    config['human_readable_name'] = human_readable_name
    config['search_terms'] = [st.to_json() for st in search_terms]
    config['test'] = {'statement_checking': {
                      'max_path_length': 5,
                      'max_paths': 1},
                      'test_corpus': 'world_modelers_tests.pkl'}
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
    if save_to_s3:
        save_config_to_s3(model_name, config)
    return config
