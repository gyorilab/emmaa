import logging
import datetime

from indra_db.client.statements import get_statements_by_paper
from indra_db.util import get_primary_db

from emmaa.statements import EmmaaStatement


logger = logging.getLogger(__name__)

PMID_CACHE = {}


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
    pmids = set(pmid_search_terms.keys())
    date = datetime.datetime.utcnow()
    db = get_primary_db()
    cached_pmids = pmids & set(PMID_CACHE.keys())
    logger.info(f"Found {len(cached_pmids)} in the cache.")
    pmid_stmts = {pmid: PMID_CACHE[pmid][:] for pmid in cached_pmids}

    new_pmids = pmids - cached_pmids
    logger.info(f"Searching for {len(new_pmids)} new pmids.")
    pmid_stmts.update(get_statements_by_paper(new_pmids, id_type='pmid', db=db,
                                              preassembled=False))
    estmts = []
    for pmid, stmts in pmid_stmts.items():
        for stmt in stmts:
            es = EmmaaStatement(stmt, date, pmid_search_terms[pmid])
            estmts.append(es)
    return estmts
