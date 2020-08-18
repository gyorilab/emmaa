from emmaa.priors import SearchTerm
from emmaa.priors.gene_list_prior import GeneListPrior

from indra.statements import Inhibition, Agent


def test_get_search_terms():
    gp = GeneListPrior(['BRAF'], 'braf', 'BRAF model')
    assert gp.name == 'braf'
    assert gp.human_readable_name == 'BRAF model'
    st = gp.make_search_terms(
        [Inhibition(Agent('vemurafenib', db_refs={'CHEBI': 'CHEBI:63637'}),
                    Agent('BRAF', db_refs={'HGNC': '1097', 'UP': 'P15056'}))])
    assert st
    assert all([isinstance(s, SearchTerm) for s in st])
    assert st[0].type == 'gene'
    assert st[0].search_term == '"BRAF"'
    assert st[1].type == 'drug'
    assert st[1].search_term == '"vemurafenib"', st[1].search_term
