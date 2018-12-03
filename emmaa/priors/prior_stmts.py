from indra_db import client


def get_stmts_for_gene(gene):
    return client.get_statements_by_gene_role_type(gene, preassembled=False)


def get_stmts_for_gene_list(gene_list):
    stmts = []
    for gene in gene_list:
        stmts += get_stmts_for_gene(gene)
    return stmts