import os
import csv
import json
import logging
import numpy as np
import networkx as nx
from scipy.sparse.linalg import expm_multiply
from indra.util import batch_iter
from indra.sources import tas
from indra.databases import cbio_client, uniprot_client
from indra.databases.hgnc_client import hgnc_ids, get_hgnc_id, get_hgnc_name, \
                                        get_uniprot_id
from emmaa.priors import get_drugs_for_gene, SearchTerm


logger = logging.getLogger(__name__)


class TcgaCancerPrior(object):
    """Prior network generation using TCGA mutations for a given cancer type.

    This class implements building a prior network using a generic underlying
    prior, and TCGA data for a specific cancer type. Mutations for the given
    cancer type are extracted from TCGA studies and heat diffusion from the
    corresponding nodes in the prior is used to identify a set of relevant
    nodes.
    """
    def __init__(self, tcga_study_prefix, sif_prior, diffusion_service=None,
                 mutation_cache=None):
        if tcga_study_prefix not in tcga_studies:
            raise ValueError('TCGA study prefix must be one of %s' %
                             (', '.join(tcga_studies.keys())))
        # e.g. paad
        self.tcga_study_prefix = tcga_study_prefix
        self.mutations = None
        self.norm_mutations = None
        self.prior_graph = None
        self.sif_prior = sif_prior
        if diffusion_service is None:
            self.diffusion_service = 'http://v3.heat-diffusion.cytoscape.io:80'
        else:
            self.diffusion_service = diffusion_service
        self.mutation_cache = mutation_cache

    def make_prior(self, pct_heat_threshold=99):
        """Run the prior node list generation and return relevant nodes."""
        self.get_mutated_genes()
        self.load_sif_prior(self.sif_prior)
        res = self.get_relevant_nodes(pct_heat_threshold)
        return res

    def get_mutated_genes(self):
        """Return dict of gene mutation frequencies based on TCGA studies."""
        if self.mutation_cache:
            logger.info('Loading mutations from %s' % self.mutation_cache)
            with open(self.mutation_cache, 'r') as fh:
                self.mutations = json.load(fh)
        else:
            logger.info('Getting mutations from cBio web service')
            mutations = {}
            for tcga_study_name in tcga_studies[self.tcga_study_prefix]:
                for idx, hgnc_name_batch in \
                                enumerate(batch_iter(hgnc_ids.keys(), 200)):
                    logger.info('Fetching mutations for %s and gene batch %s' %
                                (tcga_study_name, idx))
                    patient_mutations = \
                        cbio_client.get_profile_data(tcga_study_name,
                                                     hgnc_name_batch,
                                                     'mutation')
                    # e.g. 'ICGC_0002_TD': {'BRAF': None, 'KRAS': 'G12D'}
                    for patient, gene_mut_dict in patient_mutations.items():
                        # 'BRAF': None
                        for gene, mutated in gene_mut_dict.items():
                            if mutated is not None:
                                try:
                                    mutations[gene] += 1
                                except KeyError:
                                    mutations[gene] = 1
            self.mutations = mutations

        # Normalize mutations by length
        self.norm_mutations = {}
        for gene_name, num_muts in self.mutations.items():
            self.norm_mutations[gene_name] = \
                self.normalize_mutation_count(gene_name, num_muts)

        return self.mutations, self.norm_mutations

    @staticmethod
    def normalize_mutation_count(gene_name, num_muts):
        hgnc_id = get_hgnc_id(gene_name)
        up_id = get_uniprot_id(hgnc_id)
        if not up_id:
            logger.warning("Could not get Uniprot ID for HGNC symbol %s "
                           "with HGNC ID %s" % (gene_name, hgnc_id))
            length = 500 # a guess at a default
        else:
            length = uniprot_client.get_length(up_id)
            if not length:
                logger.warning("Could not get length for Uniprot "
                               "ID %s" % up_id)
                length = 500 # a guess at a default
        norm_mutations = num_muts / float(length)
        return norm_mutations

    def load_sif_prior(self, fname, e50=20):
        """Return a Graph based on a SIF file describing a prior.

        Parameters
        ----------
        fname : str
            Path to the SIF file.
        e50 : int
            Parameter for converting evidence counts into weights over the
            interval [0, 1) according to hyperbolic function
            `weight = (count / (count + e50))`.
        """
        # Format
        # agA_ns,agA_id,agA_name,agB_ns,agB_id,agB_name,stmt_type,
        #   evidence_count
        # FPLX,9_1_1,9_1_1,HGNC,3511,EXO1,Activation,7
        G = nx.Graph()
        logger.info('Loading SIF prior from %s' % fname)
        with open(fname, 'r') as fh:
            csv_reader = csv.reader(fh, delimiter=',')
            header = next(csv_reader)
            for row in csv_reader:
                agA_ns, agA_id, agA_name, agB_ns, agB_id, agB_name, \
                    stmt_type, evidence_count = row
                A_key = '%s:%s' % (agA_ns, agA_id)
                B_key = '%s:%s' % (agB_ns, agB_id)
                weight = (float(evidence_count) /
                          (e50 + float(evidence_count)))
                G.add_edge(A_key, B_key, weight=weight)
        self.prior_graph = G
        logger.info('Finished loading SIF prior')
        return G

    def get_relevant_nodes(self, pct_heat_threshold):
        """Return a list of the relevant nodes in the prior.

        Heat diffusion is applied to the prior network based on initial
        heat on nodes that are mutated according to patient statistics.
        """
        logger.info('Setting heat for relevant nodes in prior network')
        heats = np.zeros(len(self.prior_graph))
        mut_nodes = {}
        for gene_name, muts in self.norm_mutations.items():
            if muts:
                hgnc_id = get_hgnc_id(gene_name)
                node_key = 'HGNC:%s' % hgnc_id
                mut_nodes[node_key] = muts

        for idx, node in enumerate(self.prior_graph.nodes()):
            if node in mut_nodes:
                heats[idx] = mut_nodes[node]

        gamma = -0.1
        logger.info('Calculating Laplacian matrix')
        lp_mx = nx.normalized_laplacian_matrix(self.prior_graph,
                                               weight='weight')
        logger.info('Diffusing heat')
        Df = expm_multiply(gamma * lp_mx, heats)
        heat_thresh = np.percentile(Df, pct_heat_threshold)
        logger.info('Filtering to relevant nodes with heat threshold %.2f '
                    '(%s percentile)' % (heat_thresh, pct_heat_threshold))
        # Zip the nodes with their heats and sort
        node_heats = sorted(list(zip(self.prior_graph.nodes(), Df)),
                            key=lambda x: x[1], reverse=True)
        relevant_nodes = [n for n, heat in node_heats if heat >= heat_thresh]
        return relevant_nodes

    @staticmethod
    def search_terms_from_nodes(node_list):
        """Build a list of Pubmed search terms from the nodes returned by
        make_prior."""
        terms = []
        for node in node_list:
            if node.startswith('HGNC:'):
                hgnc_id = node.split(':')[1]
                hgnc_name = get_hgnc_name(hgnc_id)
                if hgnc_name is None:
                    logger.log(f'{node} is not a valid HGNC ID')
                else:
                    term = SearchTerm(type='gene', name=hgnc_name,
                                      search_term=f'"{hgnc_name}"',
                                      db_refs={'HGNC': hgnc_id})
                    terms.append(term)
            elif node.startswith('MESH:'):
                mesh_id = node.split(':')[1]
                # TODO: get actual process name here
                term = SearchTerm(type='bioprocess', name=mesh_id,
                                  search_term=f'{mesh_id}[MeSH Terms]',
                                  db_refs={'MESH': mesh_id})
                terms.append(term)
            # TODO: handle GO here
            else:
                logger.warning(f'Could not create search term from {node}')
        return sorted(terms, key=lambda x: x.name)

    @staticmethod
    def find_drugs_for_genes(node_list):
        """Return list of drugs targeting gene nodes."""
        tas_statements = tas.process_from_web().statements
        already_added = set()
        drug_terms = []
        for node in node_list:
            if node.startswith('HGNC:'):
                hgnc_id = node.split(':')[1]
                drugs = get_drugs_for_gene(tas_statements, hgnc_id)
                for drug in drugs:
                    if drug.name not in already_added:
                        drug_terms.append(drug)
                        already_added.add(drug.name)
        return sorted(drug_terms, key=lambda x: x.name)


def _load_tcga_studies():
    """Return a list of TCGA studies by prefix.

    Note that the resource file read here ensures that studies are
    non-redundant, which wouldn't be guaranteed by the web service.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    resources = os.path.join(here, os.pardir, 'resources')
    studies_file = os.path.join(resources, 'cancer_studies.json')
    with open(studies_file, 'r') as fh:
        studies = json.load(fh)
    return studies


tcga_studies = _load_tcga_studies()
