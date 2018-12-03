from indra.databases import hgnc_client
from emmaa.priors.cancer_prior import TcgaCancerPrior


def get_terms(ctype):
    tcp = TcgaCancerPrior(ctype, 'stmts_by_pair_type.csv',
                          mutation_cache=f'mutations_{ctype}.json')
    nodes = tcp.make_prior(pct_heat_threshold=99)
    cancer_terms = tcp.search_terms_from_nodes(nodes)
    drugs = tcp.find_drugs_for_genes(nodes)
    return cancer_terms + drugs


def save_config(ctype, terms):
    with open(f'{ctype}_config.yaml', 'w') as fh:
        fh.write('search_terms:\n')
        for term in terms:
            fh.write(f'- "{term}"\n')


if __name__ == '__main__':
    cancer_types = ('paad', 'aml', 'brca', 'luad', 'prad', 'skcm')

    for ctype in cancer_types:
        terms = get_terms(ctype)
        save_config(ctype, terms)
