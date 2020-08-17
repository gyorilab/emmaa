from indra.sources import tas
from indra.statements import Agent
from indra.databases import hgnc_client
from . import SearchTerm, get_drugs_for_gene
from . prior_stmts import get_stmts_for_gene_list
import datetime
from emmaa.statements import EmmaaStatement
from emmaa.model import EmmaaModel, save_config_to_s3


class GeneListPrior(object):
    """Class to manage the construction of a model from a list of genes.

    Parameters
    ----------
    gene_list : list[str]
        A list of HGNC gene symbols
    name : str
        The name of the model (all lower case, no spaces or special characters)
    human_readable_name : str
        The human readable name (display name) of the model
    """
    def __init__(self, gene_list, name, human_readable_name):
        self.name = name
        self.gene_list = gene_list
        self.human_readable_name = human_readable_name
        self.stmts = []
        self.search_terms = []

    def make_search_terms(self, drug_gene_stmts=None):
        """Generate search terms from the gene list."""
        if not drug_gene_stmts:
            drug_gene_stmts = tas.process_from_web().statements
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
            drug_terms = get_drugs_for_gene(drug_gene_stmts,
                                            agent.db_refs['HGNC'])
            for drug_term in drug_terms:
                if drug_term.name not in already_added:
                    terms.append(drug_term)
                    already_added.add(drug_term.name)
        self.search_terms = terms
        return terms

    def make_gene_statements(self):
        """Generate Statements from the gene list."""
        drug_names = [st.name for st in self.search_terms if
                      st.type == 'drug']
        indra_stmts = get_stmts_for_gene_list(self.gene_list, drug_names)
        estmts = [EmmaaStatement(stmt, datetime.datetime.now(), [])
                  for stmt in indra_stmts]
        self.stmts = estmts

    def make_config(self):
        """Generate a configuration based on attributes."""
        if not self.search_terms:
            self.make_search_terms()
        if not self.stmts:
            self.make_gene_statements()
        config = dict()
        config['name'] = self.name
        config['human_readable_name'] = self.human_readable_name
        config['search_terms'] = [st.to_json() for st in self.search_terms]
        config['assembly'] = {
            'belief_cutoff': 0.8,
            'filter_ungrounded': True
        }
        return config

    def make_model(self):
        """Make an EmmaaModel and upload it along with the config to S3."""
        config = self.make_config()
        em = EmmaaModel(self.name, config)
        em.stmts = self.stmts
        ndex_uuid = em.upload_to_ndex()
        config['ndex'] = {'network': ndex_uuid}
        save_config_to_s3(self.name, config)
        em.save_to_s3()


def agent_from_gene_name(gene_name):
    """Return an Agent based on a gene name."""
    hgnc_id = hgnc_client.get_hgnc_id(gene_name)
    up_id = hgnc_client.get_uniprot_id(hgnc_id)
    agent = Agent(gene_name, db_refs={'HGNC': hgnc_id,
                                      'UP': up_id})
    return agent
