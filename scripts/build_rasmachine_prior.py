import os
import indra
import pandas
from emmaa.priors.gene_list_prior import GeneListPrior


def get_ras_proteins():
    path = os.path.join(indra.__path__[0], os.pardir, 'data',
                        'ras_pathway_proteins.csv')
    df = pandas.read_csv(path, header=None, sep='\t')
    gene_names = list(df[0])
    return gene_names


if __name__ == '__main__':
    ras_proteins = get_ras_proteins()
    gp = GeneListPrior(ras_proteins, 'rasmachine', 'Ras Machine')
    gp.make_model()
