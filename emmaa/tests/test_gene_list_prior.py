from emmaa.priors import SearchTerm
from emmaa.priors.gene_list_prior import GeneListPrior


def test_get_search_terms():
    gp = GeneListPrior(['BRAF'], 'braf', 'BRAF model')
    assert gp.name == 'braf'
    assert gp.human_readable_name == 'BRAF model'
    st = gp.make_search_terms()
    assert st
    assert all([isinstance(s, SearchTerm) for s in st])
    assert st[0].type == 'gene'
    assert st[0].search_term == '"BRAF"'
    assert st[1].type == 'drug'
