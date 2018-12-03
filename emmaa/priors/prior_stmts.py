from indra_db import client
from indra.tools import assemble_corpus as ac


def get_stmts_for_gene(gene):
    return client.get_statements_by_gene_role_type(gene, preassembled=False,
                                                   count=100000)


def get_stmts_for_gene_list(gene_list):
    stmts = []
    for gene in gene_list:
        stmts += get_stmts_for_gene(gene)
    stmts = ac.filter_gene_list(stmts, gene_list, policy='all')
    return stmts