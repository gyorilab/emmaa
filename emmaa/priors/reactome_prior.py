import re
import logging
import requests
from functools import lru_cache

from indra.sources import tas
from indra.databases.uniprot_client import get_gene_name
from indra.databases.hgnc_client import get_hgnc_id, get_uniprot_id

from emmaa.priors import get_drugs_for_gene, SearchTerm

logger = logging.getLogger('reactome_prior')


def make_prior_from_genes(gene_list):
    """Return reactome prior based on a list of genes

    Parameters
    ----------
    gene_list : list of str
        List of HGNC symbols for genes

    Returns
    -------
    res : list of :py:class:`emmaa.priors.SearchTerm`
        List of search terms corresponding to all genes found in any reactome
        pathway containing one of the genes in the input gene list
    """
    all_reactome_ids = set([])
    for gene_name in gene_list:
        hgnc_id = get_hgnc_id(gene_name)
        uniprot_id = get_uniprot_id(hgnc_id)
        if not uniprot_id:
            logger.warning('Could not get Uniprot ID for HGNC symbol'
                           f' {gene_name}')
            continue
        reactome_ids = rx_id_from_up_id(uniprot_id)
        if not reactome_ids:
            logger.warning('Could not get Reactome ID for Uniprot ID'
                           f' {uniprot_id} with corresonding HGNC symbol'
                           f' {gene_name}')
            continue
        all_reactome_ids.update(reactome_ids)

    all_pathways = set([])
    for reactome_id in all_reactome_ids:
        if not re.match('^R-HSA-[0-9]', reactome_id):
            # skip non-human genes
            continue
        additional_pathways = get_pathways_containing_gene(reactome_id)
        if additional_pathways is not None:
            all_pathways.update(additional_pathways)

    all_genes = set([])
    for pathway in all_pathways:
        additional_genes = get_genes_contained_in_pathway(pathway)
        if additional_genes is not None:
            all_genes.update(additional_genes)

    gene_terms = []
    for uniprot_id in all_genes:
        hgnc_name = get_gene_name(uniprot_id)
        if hgnc_name is None:
            logger.warning('Could not get HGNC name for UniProt ID'
                           f' {uniprot_id}')
            continue
        hgnc_id = get_hgnc_id(hgnc_name)
        if not hgnc_id:
            logger.warning('Could not find HGNC ID for HGNC symbol'
                           f' {hgnc_name} with corresonding Uniprot ID'
                           f' {uniprot_id}')
            continue
        term = SearchTerm(type='gene', name=hgnc_name,
                          search_term=f'"{hgnc_name}"',
                          db_refs={'HGNC': hgnc_id,
                                   'UP': uniprot_id})
        gene_terms.append(term)
    return sorted(gene_terms, key=lambda x: x.name)


def find_drugs_for_genes(search_terms, drug_gene_stmts=None):
    """Return list of drugs targeting at least one gene from a list of genes

    Parameters
    ----------
    search_terms : list of :py:class:`emmaa.priors.SearchTerm`
        List of search terms for genes

    Returns
    -------
    drug_terms : list of :py:class:`emmaa.priors.SearchTerm`
        List of search terms of drugs targeting at least one of the input genes
    """
    if not drug_gene_stmts:
        drug_gene_stmts = tas.process_from_web().statements
    drug_terms = []
    already_added = set()
    for search_term in search_terms:
        if search_term.type == 'gene':
            hgnc_id = search_term.db_refs['HGNC']
            drugs = get_drugs_for_gene(drug_gene_stmts, hgnc_id)
            for drug in drugs:
                if drug.name not in already_added:
                    drug_terms.append(drug)
                    already_added.add(drug.name)
    return sorted(drug_terms, key=lambda x: x.name)


@lru_cache(10000)
def rx_id_from_up_id(up_id):
    """Return the Reactome Stable IDs for a given Uniprot ID."""
    react_search_url = 'http://www.reactome.org/ContentService/search/query'
    params = {'query': up_id, 'cluster': 'true', 'species': 'Homo sapiens'}
    headers = {'Accept': 'application/json'}
    res = requests.get(react_search_url, headers=headers, params=params)
    if not res.status_code == 200:
        logger.debug(f'Reactome request to {react_search_url} failed')
        return None
    json = res.json()
    results = json.get('results')
    if not results:
        logger.warning(f'No results for {up_id}')
        return None
    stable_ids = []
    for result in results:
        entries = result.get('entries')
        for entry in entries:
            stable_id = entry.get('stId')
            if not stable_id:
                continue
            stable_ids.append(stable_id)
    return stable_ids


@lru_cache(100000)
def up_id_from_rx_id(reactome_id):
    """Get the Uniprot ID (referenceEntity) for a given Reactome Stable ID."""
    react_url = 'http://www.reactome.org/ContentService/data/query/' \
                + reactome_id + '/referenceEntity'
    res = requests.get(react_url)
    if not res.status_code == 200:
        return None
    _, entry, entry_type = res.text.split('\t')
    if entry_type != 'ReferenceGeneProduct':
        return None
    id_entry = entry.split(' ')[0]
    db_ns, db_id = id_entry.split(':')
    if db_ns != 'UniProt':
        return None
    return db_id


@lru_cache(1000)
def get_pathways_containing_gene(reactome_id):
    """"Get all ids for reactom pathways containing some form of an entity

    Parameters
    ----------
    reactome_id : str
        Reactome id for a gene

    Returns
    -------
    pathway_ids : list of str
        List of reactome ids for pathways containing the input gene
    """
    react_url = ('http://www.reactome.org/ContentService/data/pathways/low'
                 f'/entity/{reactome_id}/allForms')
    params = {'species': 'Homo sapiens'}
    headers = {'Accept': 'application/json'}
    res = requests.get(react_url, headers=headers, params=params)
    if not res.status_code == 200:
        logger.warning(f'Request failed for reactome_id {reactome_id}')
        return None
    results = res.json()
    if not results:
        logger.info(f'No results for {reactome_id}')
        return None
    pathway_ids = [pathway['stIdVersion'] for pathway in results]
    return pathway_ids


@lru_cache(1000)
def get_genes_contained_in_pathway(reactome_id):
    """Get all genes contained in a given pathway

    Parameters
    ----------
    reactome_id : str
        Reactome id for a pathway

    Returns
    -------
    genes : list of str
        List of uniprot ids for all unique genes contained in input pathway
    """
    react_url = ('http://www.reactome.org/ContentService/data'
                 f'/participants/{reactome_id}')
    params = {'species': 'Homo species'}
    headers = {'Accept': 'application/json'}
    res = requests.get(react_url, headers=headers, params=params)
    results = res.json()
    if not res.status_code == 200:
        return None
    if not results:
        logger.info(f'No results for {reactome_id}')
    genes = [entity['identifier'] for result in results
             for entity in result['refEntities']
             if entity.get('schemaClass') == 'ReferenceGeneProduct']
    return list(set(genes))
