import unittest
from emmaa.priors import SearchTerm
from emmaa.priors.reactome_prior import rx_id_from_up_id
from emmaa.priors.reactome_prior import find_drugs_for_genes
from emmaa.priors.reactome_prior import make_prior_from_genes
from emmaa.priors.reactome_prior import get_pathways_containing_gene
from emmaa.priors.reactome_prior import get_genes_contained_in_pathway


@unittest.skip('Reactome ID lookup by UniProt ID has changed.')
def test_rx_id_from_up_id():
    """Check that Uniprot ids are being successfully mapped to reactome ids
    """
    test_cases = [('P01116', 'R-HSA-62719'),   # KRAS
                  ('P04637', 'R-HSA-69488'),   # TP53
                  ('Q13485', 'R-HSA-177103')]  # SMAD4
    for up_id, rx_id in test_cases:
        all_rx_ids = rx_id_from_up_id(up_id)
        assert rx_id in all_rx_ids


def test_get_pathways_containing_genes():
    # get pathways containing KRAS
    KRAS_pathways = get_pathways_containing_gene('R-HSA-62719')

    # Signaling by RAS mutants
    assert 'R-HSA-6802949.1' in KRAS_pathways

    # Paradoxical activation of RAF signaling by kinase inactive BRAF
    assert 'R-HSA-6802955.1' in KRAS_pathways

    # Insulin receptor signalling cascade
    assert 'R-HSA-74751.3' in KRAS_pathways


def test_get_genes_contained_in_pathway():
    # Get genes in Signaling by RAS mutants pathway
    RAS_mutants_genes = get_genes_contained_in_pathway('R-HSA-6802949.1')

    # KRAS
    assert 'P01116' in RAS_mutants_genes
    # RAF1
    assert 'P04049' in RAS_mutants_genes
    # MAPK1
    assert 'P28482' in RAS_mutants_genes
    # BRAF
    assert 'P15056' in RAS_mutants_genes


def test_make_prior_from_genes():
    # KRAS prior
    prior = make_prior_from_genes(['KRAS'])

    # make sure there are results
    assert prior

    # make sure the prior is a list of SearchTerms
    assert all(isinstance(term, SearchTerm) for term in prior)

    # if we get fewer than 100 genes for KRAS something is very wrong
    assert len(prior) > 100

    # test that the prior contains some of the usual suspects
    gene_names = set(term.name for term in prior)
    assert set(['KRAS', 'RAF1', 'MAPK1', 'BRAF']) <= set(gene_names)


def test_find_drugs_for_genes():
    # SearchTerm for SRC
    SRC = SearchTerm(type='gene', name='SRC', search_term='"SRC"',
                     db_refs={'HGNC': '11283'})
    # drugs targeting KRAS
    drug_terms = find_drugs_for_genes([SRC])

    # make sure there are results
    assert drug_terms

    # make sure the result is a list of search terms
    assert all(isinstance(term, SearchTerm) for term in drug_terms)

    # something is wrong if there are fewer than 10 drugs
    assert len(drug_terms) > 10

    # test that some example drugs are included
    drug_names = set(term.name for term in drug_terms)
    example_drugs = set(['Dasatinib', 'Tozasertib', 'Ponatinib'])
    assert example_drugs <= drug_names
