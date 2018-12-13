from emmaa.priors.reactome_prior import rx_id_from_up_id
from emmaa.priors.reactome_prior import up_id_from_rx_id
from emmaa.priors.reactome_prior import make_prior_from_genes
from emmaa.priors.reactome_prior import get_pathways_containing_gene
from emmaa.priors.reactome_prior import get_genes_contained_in_pathway


def test_rx_id_from_up_id():
    """Check that Uniprot ids are being successfully mapped to reactome ids

    Checks for KRAS, TP53, and SMAD4. """
    test_cases = [('P01116', 'R-HSA-62719'),
                  ('P04637', 'R-HSA-69488'),
                  ('Q13485', 'R-HSA-177103')]
    for up_id, rx_id in test_cases:
        all_rx_ids = rx_id_from_up_id(up_id)
        assert rx_id in all_rx_ids


def test_get_pathways_containing_genes():
    # get pathways containing KRAS
    KRAS_pathways = get_pathways_containing_gene('R-HSA-62719')

    # Signaling by KRAS mutants
    assert 'R-HSA-6802949.1' in KRAS_pathways

    # Paradoxical activation of RAF signaling by kinase inactive BRAF
    assert 'R-HSA-6802955.1' in KRAS_pathways

    # Insulin receptor signalling cascade
    assert 'R-HSA-74751.3' in KRAS_pathways
