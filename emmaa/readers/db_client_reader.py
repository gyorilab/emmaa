import datetime
from indra_db.client.statements import get_statements_by_paper
from emmaa.statements import EmmaaStatement

def get_estatements_by_pmid(pmids):
    """Return extracted EmmaaStatements from INDRA database given a list of PMIDs.

    Parameters
    ----------
    pmids : list[str]
        A list of PMIDs to check with a database.

    Returns
    -------
    dict:[str, list[emmaa.model.EmmaaStatement]
        A dict of PMIDs and the list of EmmaaStatements extracted from INDRA database for given PMIDs.
    """
    date = datetime.datetime.utcnow()
    pmid_stmts = {}
    for pmid in pmids:
        stmts[pmid] = get_statements_by_paper(pmid, id_type='pmid', 
                    count=1000, db=None, do_stmt_count=False, preassembled=False)
    for pmid, stmts in pmid_stmts.items():
        for stmt in stmts:
            estmts.append(es)
            es = EmmaaStatement(stmt, date, pmid_search_terms[pmid])
    return estmts

print(get_estatements_by_pmid["14461663", "14461663"])    