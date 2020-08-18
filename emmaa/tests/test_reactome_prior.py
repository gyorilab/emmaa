import re
import unittest
from emmaa.priors import SearchTerm
from emmaa.priors.reactome_prior import rx_id_from_up_id
from emmaa.priors.reactome_prior import find_drugs_for_genes
from emmaa.priors.reactome_prior import make_prior_from_genes
from emmaa.priors.reactome_prior import get_pathways_containing_gene
from emmaa.priors.reactome_prior import get_genes_contained_in_pathway
from indra.statements import Inhibition, Agent


def test_rx_id_from_up_id():
    """Check that Uniprot ids are being successfully mapped to reactome ids
    """
    test_cases = [('P01116', 'R-HSA-9653079'),   # KRAS
                  ('P04637', 'R-HSA-69507'),   # TP53
                  ('Q13485', 'R-HSA-2187323')]  # SMAD4
    for up_id, rx_id in test_cases:
        all_rx_ids = rx_id_from_up_id(up_id)
        assert rx_id in all_rx_ids


def test_get_pathways_containing_genes():
    # get pathways containing KRAS
    KRAS_pathways = get_pathways_containing_gene('R-HSA-62719')
    pattern = r'R-HSA-[0-9]{7}\.[0-9]{1}$'
    # Check if function returns a list of valid pathway ids
    assert all([re.match(pattern, pathway_id) for pathway_id in KRAS_pathways])
    # Check if function returns a reasonable number of pathways
    assert len(KRAS_pathways) > 3
    # Signaling Downstream of RAS mutants
    assert 'R-HSA-9649948.1' in KRAS_pathways


def test_get_genes_contained_in_pathway():
    # Get genes in Signaling by RAS mutants pathway
    RAS_mutants_genes = get_genes_contained_in_pathway('R-HSA-6802949.1')
    pattern = re.compile(r'(O|P|Q)[A-Z0-9]{5}$')
    # Check that function produces list of valid human uniprot ids
    assert all([re.match(pattern, up_id) for up_id in RAS_mutants_genes])
    # Check that function returns a reasonable number of genes
    assert len(RAS_mutants_genes) > 30
    # KRAS
    assert 'P01116' in RAS_mutants_genes


def test_make_prior_from_genes():
    # KRAS prior
    prior1 = make_prior_from_genes(['KRAS'])
    # BRCA prior
    prior2 = make_prior_from_genes(['TP53', 'PIK3CA', 'GATA3', 'CBFB', 'CDH1'])
    # make sure there are results
    assert prior1
    # make sure the prior is a list of SearchTerms
    assert all(isinstance(term, SearchTerm) for term in prior1)
    # if we get fewer than 40 genes for KRAS it's likely something is wrong
    assert len(prior1) > 40
    # test that the prior contains some of the usual suspects
    gene_names = set(term.name for term in prior1)
    assert set(['KRAS', 'RAF1', 'MAPK1', 'BRAF']) <= gene_names

    assert prior2
    assert all(isinstance(term, SearchTerm) for term in prior2)
    assert len(prior2) > 1000
    gene_names = set(term.name for term in prior2)
    assert set(['COL1A1', 'ESR1', 'EGFR', 'HRAS']) <= gene_names
    # some genes expressed only in the brain
    assert not (gene_names & set(['BARHL1', 'NEUROD2']))


def test_find_drugs_for_genes():
    # SearchTerm for SRC
    SRC = SearchTerm(type='gene', name='SRC', search_term='"SRC"',
                     db_refs={'HGNC': '11283'})
    # drugs targeting KRAS
    drug_terms = find_drugs_for_genes(
        [SRC],
        [Inhibition(Agent('Dasatinib', db_refs={'CHEBI': 'CHEBI:49375'}),
                    Agent('SRC', db_refs={'HGNC': '11283'})),
         Inhibition(Agent('Ponatinib', db_refs={'CHEBI': 'CHEBI:78543'}),
                    Agent('SRC', db_refs={'HGNC': '11283'}))])

    # make sure there are results
    assert drug_terms

    # make sure the result is a list of search terms
    assert all(isinstance(term, SearchTerm) for term in drug_terms)

    # test that some example drugs are included
    drug_names = set(term.name for term in drug_terms)
    assert drug_names == set(['Dasatinib', 'Ponatinib'])
