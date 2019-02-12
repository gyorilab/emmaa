import datetime
from indra_db.client.statements import get_statements_by_paper
from emmaa.statements import EmmaaStatement

def get_estatements_by_pmid_search_terms(pmid_search_terms):
    """Return extracted EmmaaStatements from INDRA database given a PMID-search term dict.

    Parameters
    ----------
    pmids : list[str]
        A list of PMIDs to check with a database.

    Returns
    -------
    dict:[str, list[emmaa.model.EmmaaStatement]]
        A dict of PMIDs and the list of EmmaaStatements extracted from INDRA database for given PMIDs.
    """
    pmids = list(pmid_search_terms.keys())
    date = datetime.datetime.utcnow()
    pmid_stmts = {}
    for pmid in pmids:
        pmid_stmts[pmid] = get_statements_by_paper(pmid, id_type='pmid', 
                            count=1000, db=None, do_stmt_count=False, preassembled=False)
    estmsts = []
    for pmid, stmts in pmid_stmts.items():
        for stmt in stmts:
            es = EmmaaStatement(stmt, date, pmid_search_terms[pmid])
            estmts.append(es)
    return estmts