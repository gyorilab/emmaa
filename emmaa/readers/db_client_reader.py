import datetime
from indra_db.client.statements import get_statements_by_paper
from indra_db.util import get_primary_db
from emmaa.statements import EmmaaStatement


def read_db_pmid_search_terms(pmid_search_terms):
    """Return extracted EmmaaStatements from INDRA database given a
    PMID-search term dict.

    Parameters
    ----------
    pmid_search_terms : dict
        A dict representing a set of PMIDs pointing to search terms that
        produced them.

    Returns
    -------
    list[:py:class:`emmaa.model.EmmaaStatement`]
        A list of EmmaaStatements extracted from the given PMIDs.
    """
    pmids = list(pmid_search_terms.keys())
    date = datetime.datetime.utcnow()
    db = get_primary_db()
    pmid_stmts = get_statements_by_paper(pmids, id_type='pmid', db=db,
                                         preassembled=False)
    estmts = []
    for pmid, stmts in pmid_stmts.items():
        for stmt in stmts:
            es = EmmaaStatement(stmt, date, pmid_search_terms[pmid])
            estmts.append(es)
    return estmts
