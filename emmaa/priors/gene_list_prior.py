from indra.statements import Agent
from indra.databases import hgnc_client
from . import SearchTerm
from . prior_stmts import get_stmts_for_gene_list


class GeneListPrior(object):
    def __init__(self, name, gene_list):
        self.name = name
        self.gene_list = gene_list

    def get_search_terms(self):
        terms = []
        for gene in self.gene_list:
            agent = agent_from_gene_name(gene)
            term = SearchTerm(type='gene', name=agent.name,
                              search_term=f'"{agent.name}"',
                              db_refs={'HGNC': agent.db_refs['HGNC'],
                                       'UP': agent.db_refs['UP']})
            terms.append(term)
        return terms

    def get_gene_statements(self):
        stmts = get_stmts_for_gene_list(self.gene_list)


def agent_from_gene_name(gene_name):
    hgnc_id = hgnc_client.get_hgnc_id(gene_name)
    up_id = hgnc_client.get_uniprot_id(hgnc_id)
    agent = Agent(gene_name, db_refs={'HGNC': hgnc_id,
                                      'UP': up_id})
    return agent