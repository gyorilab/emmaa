from indra.databases import hgnc_client
from emmaa.priors.cancer_prior import TcgaCancerPrior



#cancer_types = ('paad', 'aml', 'brca', 'luad', 'prad', 'skcm')
cancer_types = ('paad',)

cancer_terms = {}
for ctype in cancer_types:
    tcp = TcgaCancerPrior(ctype, 'stmts_by_pair_type.csv',
                          mutation_cache=f'mutations_{ctype}.json')
    nodes = tcp.make_prior(pct_heat_threshold=99)
    terms = tcp.search_terms_from_nodes(nodes)
    cancer_terms[ctype] = terms

