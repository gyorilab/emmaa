from nose.plugins.attrib import attr
from emmaa.xdd import get_document_figures, get_figures_from_query


def test_document_figures_doi():
    doi = '10.1101/2020.08.23.20180281'
    fig_list = get_document_figures(doi, 'DOI')
    assert fig_list
    # Should be a list of tuples with title and image bytes
    assert len(fig_list[0]) == 2


# This would call database
@attr('notravis')
def test_document_figures_other_types():
    # Should get results from different paper ID types
    trid = 31859624
    fig_list = get_document_figures(trid, 'TRID')
    assert fig_list
    assert len(fig_list[0]) == 2
    pmid = '32838361'
    fig_list = get_document_figures(pmid, 'PMID')
    assert fig_list
    assert len(fig_list[0]) == 2
    pmcid = 'PMC7362813'
    fig_list = get_document_figures(pmcid, 'PMCID')
    assert fig_list
    assert len(fig_list[0]) == 2


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
