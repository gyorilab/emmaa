import datetime
from indra_db.client.principal.raw_statements import \
    get_raw_stmt_jsons_from_papers
from indra_db.util import get_db
from indra.statements import stmts_from_json
from emmaa.statements import EmmaaStatement


def read_db_ids_search_terms(id_search_terms, id_type):
    """Return extracted EmmaaStatements from INDRA database given an
    ID-search term dict.

    Parameters
    ----------
    id_search_terms : dict
        A dict representing a set of IDs pointing to search terms that
        produced them.

    Returns
    -------
    list[:py:class:`emmaa.model.EmmaaStatement`]
        A list of EmmaaStatements extracted from the given IDs.
    """
    ids = list(id_search_terms.keys())
    date = datetime.datetime.utcnow()
    db = get_db('primary')
    id_stmts = get_raw_stmt_jsons_from_papers(ids, id_type=id_type, db=db)
    estmts = []
    for _id, stmt_jsons in id_stmts.items():
        stmts = stmts_from_json(stmt_jsons)
        for stmt in stmts:
            es = EmmaaStatement(stmt, date, id_search_terms[_id])
            estmts.append(es)
    return estmts


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
    return read_db_ids_search_terms(pmid_search_terms, 'pmid')


def read_db_doi_search_terms(doi_search_terms):
    """Return extracted EmmaaStatements from INDRA database given a
    DOI-search term dict.

    Parameters
    ----------
    doi_search_terms : dict
        A dict representing a set of DOIs pointing to search terms that
        produced them.

    Returns
    -------
    list[:py:class:`emmaa.model.EmmaaStatement`]
        A list of EmmaaStatements extracted from the given DOIs.
    """
    return read_db_ids_search_terms(doi_search_terms, 'doi')
