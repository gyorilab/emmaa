import logging
from indra_db import client
from indra.tools import assemble_corpus as ac


logger = logging.getLogger(__name__)


def get_stmts_for_gene(gene):
    """Return all existing Statements for a given gene from the DB.

    Parameters
    ----------
    gene : str
        The HGNC symbol of a gene to query.

    Returns
    -------
    list[indra.statements.Statement]
        A list of INDRA Statements in which the given gene is involved.
    """
    return client.get_statements_by_gene_role_type(gene, preassembled=False,
                                                   count=100000)


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
