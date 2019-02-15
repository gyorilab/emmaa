import unittest
from emmaa.statements import EmmaaStatement
from emmaa.priors import SearchTerm
from emmaa.readers.db_client_reader import read_db_pmid_search_terms


# FIXME Test should only run if tests are run locally, not by Travis
@unittest.skip('Test not run by Travis')
def test_read_db_pmid_search_terms():
    """Check read_db_pmid_search_terms() function with different inputs."""
    search_terms = [SearchTerm('gene', 'AKT2', {'HGNC': '392', 'UP': 'P31751'},
        'AKT2'), SearchTerm('gene', 'ACOX2', {'HGNC': '120', 'UP': 'Q99424'},
        'ACOX2')]
    # Check for empty input.
    assert len(read_db_pmid_search_terms({})) == 0
    # Check for PMIDs that do not have any statements.
    nostmts_pmid = "22178463"
    assert len(read_db_pmid_search_terms({nostmts_pmid: search_terms})) == 0
    # Check for PMIDs that have statements.
    stmts_pmid = "23431386"
    estmts = read_db_pmid_search_terms({stmts_pmid: search_terms})
    assert len(estmts) > 0
    assert isinstance(estmts[0], EmmaaStatement)
    estmts[0].search_terms == search_terms
