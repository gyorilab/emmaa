import logging
from typing import List

from indra.databases import hgnc_client
from indra.statements import Statement, stmts_from_json
from indra.tools import assemble_corpus as ac
from indra_db.client.principal import get_raw_stmt_jsons_from_agents

__all__ = [
    "get_stmts_for_gene",
    "get_stmts_for_gene_list",
]

logger = logging.getLogger(__name__)


def get_stmts_for_gene(gene: str, max_stmts: int = 100000) -> List[Statement]:
    """Return all existing Statements for a given gene from the DB.

    Parameters
    ----------
    gene :
        The HGNC symbol of a gene to query.
    max_stmts:
        The maximum number of statements to return

    Returns
    -------
    :
        A list of INDRA Statements in which the given gene is involved.
    """
    hgnc_id = hgnc_client.get_current_hgnc_id(gene)
    if hgnc_id is None:
        return []
    agents = [
        (None, hgnc_id, "HGNC"),
    ]
    res = get_raw_stmt_jsons_from_agents(agents=agents, max_stmts=max_stmts)
    return stmts_from_json(res.values())


def get_stmts_for_gene_list(gene_list, other_entities):
    """Return all Statements between genes in a given list.

    Parameters
    ----------
    gene_list : list[str]
        A list of HGNC symbols for genes to query.
    other_entities : list[str]
        A list of other entities to keep as part of the set of Statements.

    Returns
    -------
    list[indra.statements.Statement]
        A list of INDRA Statements between the given list of genes and other
        entities specified.
    """
    stmts = []
    for gene in gene_list:
        logger.info(f'Querying {gene}')
        st = get_stmts_for_gene(gene)
        logger.info(f'Got {len(st)} statements for {gene}')
        stmts += st
    stmts = ac.filter_gene_list(stmts, gene_list + other_entities, policy='all')
    return stmts
