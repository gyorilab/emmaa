import logging
from indra.util import batch_iter
from indra.databases import cbio_client
from indra.databases.hgnc_client import hgnc_ids


logger = logging.getLogger(__name__)


class TcgaCancerPrior(object):
    def __init__(self, tcga_study_name):
        # e.g. paad_icgc
        self.tcga_study_name = tcga_study_name

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
        return mutations
