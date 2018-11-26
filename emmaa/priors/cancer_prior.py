import csv
import logging
from ndex2.nice_cx_network import NiceCXNetwork
from indra.util import batch_iter
from indra.databases import cbio_client
from indra.databases.hgnc_client import hgnc_ids


logger = logging.getLogger(__name__)


class TcgaCancerPrior(object):
    def __init__(self, tcga_study_name):
        # e.g. paad_icgc
        self.tcga_study_name = tcga_study_name
        self.mutations = None
        self.prior_cx = None

    def make_prior(self):
        mutations = self.get_mutated_genes()

    def get_mutated_genes(self):
        mutations = {}
        for idx, hgnc_name_batch in enumerate(batch_iter(hgnc_ids.keys(), 100)):
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
        cxn = NiceCXNetwork()
        with open(fname, 'r') as fh:
            csv_reader = csv.reader(fh, delimiter=',')
            header = next(csv_reader)
            for row in csv_reader:
                agA_ns, agA_id, agA_name, agB_ns, agB_id, agB_name, \
                    stmt_type, evidence_count = row
                A_key = '%s:%s' % (agA_ns, agA_id)
                B_key = '%s:%s' % (agB_ns, agB_id)
                A_id = cxn.create_node(A_key)
                B_id = cxn.create_node(B_key)
                cxn.create_edge(A_id, B_id, stmt_type)
        cx = cxn.to_cx()
        self.prior_cx = cx
