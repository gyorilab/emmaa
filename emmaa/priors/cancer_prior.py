import csv
import json
import logging
import requests
from ndex2.nice_cx_network import NiceCXNetwork
from indra.util import batch_iter
from indra.databases import cbio_client
from indra.databases.hgnc_client import hgnc_ids, get_hgnc_id


logger = logging.getLogger(__name__)


class TcgaCancerPrior(object):
    def __init__(self, tcga_study_name, sif_prior, diffusion_service=None,
                 mutation_cache=None):
        # e.g. paad_icgc
        self.tcga_study_name = tcga_study_name
        self.mutations = None
        self.prior_cx = None
        self.sif_prior = sif_prior
        if diffusion_service is None:
            self.diffusion_service = 'http://v3.heat-diffusion.cytoscape.io:80'
        else:
            self.diffusion_service = diffusion_service
        self.node_map = {}
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
        logger.info('Loading SIF prior from %s' % fname)
        cxn = NiceCXNetwork()
        with open(fname, 'r') as fh:
            csv_reader = csv.reader(fh, delimiter=',')
            header = next(csv_reader)
            for row in csv_reader:
                agA_ns, agA_id, agA_name, agB_ns, agB_id, agB_name, \
                    stmt_type, evidence_count = row
                A_key = '%s:%s' % (agA_ns, agA_id)
                A_id = self.node_map.get(A_key)
                if A_id is None:
                    A_id = cxn.create_node(A_key)
                    self.node_map[A_key] = A_id
                B_key = '%s:%s' % (agB_ns, agB_id)
                B_id = self.node_map.get(B_key)
                if B_id is None:
                    B_id = cxn.create_node(B_key)
                    self.node_map[B_key] = B_id
                cxn.create_edge(A_id, B_id, stmt_type)
        #cx = cxn.to_cx()
        self.prior_cx = cxn

    def get_relevant_nodes(self):
        # Given the prior CX and some mutations, we add heat to the network
        logger.info('Setting heat for relevant nodes in prior network')
        for gene_name, muts in self.mutations.items():
            if muts:
                hgnc_id = get_hgnc_id(gene_name)
                node_key = 'HGNC:%s' % hgnc_id
                node_id = self.node_map.get(node_key)
                if node_id is not None:
                    self.prior_cx.set_node_attribute(node_id,
                                                     'diffusion_input', 1)
        logger.info('Generating CX network from prior')
        cx = self.prior_cx.to_cx()
        # perform heat diffusion
        logger.info('Calling heat diffusion web service')
        res = requests.post(self.diffusion_service, json=cx)
        return res
