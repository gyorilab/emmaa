from emmaa.xdd import get_document_figures, get_figures_from_query


def test_document_figures():
    # Should get results from different paper ID types
    doi = '10.1101/2020.08.23.20180281'
    fig_list = get_document_figures(doi, 'DOI')
    assert fig_list
    # Should be a list of tuples with title and image bytes
    assert len(fig_list[0]) == 2
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
    query = 'ACE2,TMPRSS2'
    # Get full result
    fig_list = get_figures_from_query(query)
    assert fig_list
    assert len(fig_list[0]) == 3
    total = len(fig_list)
    assert total > 90
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
