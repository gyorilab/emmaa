from indra.sources import tas
from indra.statements import Agent
from indra.databases import hgnc_client
from . import SearchTerm, get_drugs_for_gene
from . prior_stmts import get_stmts_for_gene_list


class GeneListPrior(object):
    def __init__(self, name, gene_list):
        self.name = name
        self.gene_list = gene_list
        self.stmts = []
        self.search_terms = []

    def get_search_terms(self):
        tas_stmts = tas.process_csv().statements
        already_added = set()
        terms = []
        for gene in self.gene_list:
            # Gene search term
            agent = agent_from_gene_name(gene)
            term = SearchTerm(type='gene', name=agent.name,
                              search_term=f'"{agent.name}"',
                              db_refs={'HGNC': agent.db_refs['HGNC'],
                                       'UP': agent.db_refs['UP']})
            terms.append(term)

            # Drug search term
            drug_terms = get_drugs_for_gene(tas_stmts,
                                            agent.db_refs['HGNC'])
            for drug_term in drug_terms:
                if drug_term.name not in already_added:
                    terms.append(drug_term)
                    already_added.add(drug_term.name)
        self.search_terms = terms
        return terms

    def get_gene_statements(self):
        drug_names = [st.name for st in self.search_terms if
                      st.type=='drug']
        self.stmts = get_stmts_for_gene_list(self.gene_list, drug_names)


def agent_from_gene_name(gene_name):
    hgnc_id = hgnc_client.get_hgnc_id(gene_name)
    up_id = hgnc_client.get_uniprot_id(hgnc_id)
    agent = Agent(gene_name, db_refs={'HGNC': hgnc_id,
                                      'UP': up_id})
    return agent
