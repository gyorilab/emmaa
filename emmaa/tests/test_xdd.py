from nose.plugins.attrib import attr
from emmaa.xdd import get_document_figures, get_figures_from_query


@attr('nonpublic')
def test_document_figures_doi():
    doi = '10.1136/bmj.n436'
    fig_list = get_document_figures(doi, 'DOI')
    assert fig_list
    # Should be a list of tuples with title and image bytes
    assert len(fig_list[0]) == 8


# This would call database
@attr('notravis', 'nonpublic')
def test_document_figures_other_types():
    # Should get results from different paper ID types
    trid = 32094555
    fig_list = get_document_figures(trid, 'TRID')
    assert fig_list
    assert len(fig_list[0]) == 2
    pmid = '32923317'
    fig_list = get_document_figures(pmid, 'PMID')
    assert fig_list
    assert len(fig_list[0]) == 2
    pmcid = 'PMC7476560'
    fig_list = get_document_figures(pmcid, 'PMCID')
    assert fig_list
    assert len(fig_list[0]) == 2


@attr('nonpublic')
def test_figures_from_query():
    query = 'ATG12,ATG5'
    # Get full result
    fig_list = get_figures_from_query(query)
    assert fig_list
    assert len(fig_list[0]) == 3
    total = len(fig_list)
    assert total > 15, total
    # Set smaller limit
    fig_list = get_figures_from_query(query, limit=10)
    assert fig_list
    assert len(fig_list[0]) == 3
    assert len(fig_list) == 10
    # If limit is larger than total, get total
    fig_list = get_figures_from_query(query, limit=(total+10))
    assert fig_list
    assert len(fig_list[0]) == 3
    assert len(fig_list) == total
