import yaml
import pickle
import datetime
from emmaa.model import EmmaaStatement, EmmaaModel
from emmaa.priors.prior_stmts import get_stmts_for_gene_list
from emmaa.priors.cancer_prior import TcgaCancerPrior


def get_terms(ctype):
    tcp = TcgaCancerPrior(ctype, 'stmts_by_pair_type.csv',
                          mutation_cache=f'mutations_{ctype}.json')
    nodes = tcp.make_prior(pct_heat_threshold=99)
    cancer_terms = tcp.search_terms_from_nodes(nodes)
    drugs = tcp.find_drugs_for_genes(nodes)
    return cancer_terms, drugs


def load_config(ctype):
    fname = f'models/{ctype}/config.yaml'
    with open(fname, 'r') as fh:
        config = yaml.load(fh)
    return config


def save_config(ctype, terms):
    config = load_config(ctype)
    config['search_terms'] = [f'"{term}"' for term in terms]
    with open(fname, 'w') as fh:
        yaml.dump(config, fh)


def save_prior(stmts):
    with open(f'models/{ctype}/prior_stmts.pkl', 'wb') as fh:
        pickle.dump(stmts, fh)


def upload_prior(ctype, config):
    fname = f'models/{ctype}/prior_stmts.pkl'
    with open(fname, 'rb') as fh:
        stmts = pickle.load(fh)
    estmts = [EmmaaStatement(stmt, datetime.datetime.now(), [])
              for stmt in stmts]
    model = EmmaaModel(ctype, config)
    model.add_statements(estmts)
    model.upload_to_ndex()


if __name__ == '__main__':
    cancer_types = ('aml', 'brca', 'luad', 'prad', 'skcm')

    for ctype in cancer_types:
        cancer_terms, drugs = get_terms(ctype)
        prior_stmts = get_stmts_for_gene_list(cancer_terms, drugs)
        save_prior(prior_stmts)
        terms = cancer_terms + drugs
        #save_config(ctype, terms)
