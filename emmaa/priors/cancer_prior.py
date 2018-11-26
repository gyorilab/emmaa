import csv
import json
import logging
import requests
import numpy as np
import networkx as nx
from scipy.sparse.linalg import expm_multiply
from indra.util import batch_iter
from indra.databases import cbio_client
from indra.databases.hgnc_client import hgnc_ids, get_hgnc_id


logger = logging.getLogger(__name__)


class TcgaCancerPrior(object):
    """Prior network generation using TCGA mutations for a given cancer type.

    This class implements building a prior network using a generic underlying
    prior, and TCGA data for a specific cancer type. Mutations for the given
    cancer type are extracted from TCGA studies and heat diffusion from the
    corresponding nodes in the prior is used to identify a set of relevant
    nodes.
    """
    def __init__(self, tcga_study_name, sif_prior, diffusion_service=None,
                 mutation_cache=None):
        # e.g. paad_icgc
        self.tcga_study_name = tcga_study_name
        self.mutations = None
        self.prior_graph = None
        self.sif_prior = sif_prior
        if diffusion_service is None:
            self.diffusion_service = 'http://v3.heat-diffusion.cytoscape.io:80'
        else:
            self.diffusion_service = diffusion_service
        self.mutation_cache = mutation_cache

    def make_prior(self):
        self.get_mutated_genes()
        self.load_sif_prior(self.sif_prior)
        res = self.get_relevant_nodes()
        return res

    def get_mutated_genes(self):
        if self.mutation_cache:
            logger.info('Loading mutations from %s' % self.mutation_cache)
            with open(self.mutation_cache, 'r') as fh:
                self.mutations = json.load(fh)
                return self.mutations
        logger.info('Getting mutations from cBio web service')
        mutations = {}
        for idx, hgnc_name_batch in enumerate(batch_iter(hgnc_ids.keys(),
                                                         100)):
            logger.info('Fetching mutations for gene batch %s' % idx)
            patient_mutations = \
                cbio_client.get_profile_data(self.tcga_study_name,
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
        return mutations

    def load_sif_prior(self, fname):
        # Format
        # agA_ns,agA_id,agA_name,agB_ns,agB_id,agB_name,stmt_type,
        #   evidence_count
        # FPLX,9_1_1,9_1_1,HGNC,3511,EXO1,Activation,7
        G = nx.Graph()
        logger.info('Loading SIF prior from %s' % fname)
        edges = []
        with open(fname, 'r') as fh:
            csv_reader = csv.reader(fh, delimiter=',')
            header = next(csv_reader)
            for row in csv_reader:
                agA_ns, agA_id, agA_name, agB_ns, agB_id, agB_name, \
                    stmt_type, evidence_count = row
                A_key = '%s:%s' % (agA_ns, agA_id)
                B_key = '%s:%s' % (agB_ns, agB_id)
                edge = (A_key, B_key)
                if edge not in edges:
                    G.add_edge(*edge, weight=1)
                    edges.append(set(edge))
        self.prior_graph = G
        return G

    def get_relevant_nodes(self, heat_thresh=0.1):
        logger.info('Setting heat for relevant nodes in prior network')
        heats = np.zeros(len(self.prior_graph))
        mut_nodes = []
        for gene_name, muts in self.mutations.items():
            if muts:
                hgnc_id = get_hgnc_id(gene_name)
                node_key = 'HGNC:%s' % hgnc_id
                mut_nodes.append(node_key)

        for idx, node in enumerate(self.prior_graph.nodes()):
            if node in mut_nodes:
                heats[idx] = 1.0

        gamma = -0.1
        logger.info('Calculating Laplacian matrix')
        lp_mx = nx.laplacian_matrix(self.prior_graph, weight='weight')
        logger.info('Diffusing heat')
        Df = expm_multiply(gamma * lp_mx, heats)
        logger.info('Filtering to relevant nodes with heat threshold %.2f' %
                    heat_threst)
        relevant_nodes = [n for n, heat in zip(self.prior_graph.nodes(), Df) if
                          heat >= heat_thresh]
        return relevant_nodes
