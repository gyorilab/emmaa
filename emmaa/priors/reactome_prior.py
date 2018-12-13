import requests
import logging
from functools import lru_cache


logger = logging.getLogger('reactome_prior')


@lru_cache(10000)
def rx_id_from_up_id(up_id):
    """Get the Reactome Stable ID for a given Uniprot ID."""
    react_search_url = 'http://www.reactome.org/ContentService/search/query'
    params = {'query': up_id, 'cluster': 'true', 'species': 'Homo sapiens'}
    headers = {'Accept': 'application/json'}
    res = requests.get(react_search_url, headers=headers, params=params)
    if not res.status_code == 200:
        return None
    json = res.json()
    results = json.get('results')
    if not results:
        logger.info(f'No results for {up_id}')
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
    """"Get all ids for reactom pathways containing some form of an entity"""
    react_url = ('http://www.reactome.org/ContentService/data/pathways/low'
                 f'/entity/{reactome_id}/allForms')
    params = {'species': 'Homo sapiens'}
    headers = {'Accept': 'application/json'}
    res = requests.get(react_url, headers=headers, params=params)
    if not res.status_code == 200:
        return None
    results = res.json()
    if not results:
        logger.info(f'No results for {reactome_id}')
        return None
    pathway_ids = [pathway['stIdVersion'] for pathway in results]
    return pathway_ids


@lru_cache(1000)
def get_genes_contained_in_pathway(reactome_id):
    """Get all genes contained in a given pathway"""
    react_url = ('http://www.reactome.org/ContentService/data'
                 f'/participants/{reactome_id}')
    headers = {'Accept': 'application/json'}
    res = requests.get(react_url, headers=headers)
    results = res.json()
    if not res.status_code == 200:
        return None
    if not results:
        logger.info(f'No results for {reactome_id}')
    genes = [entity['identifier'] for result in results
             for entity in result['refEntities']
             if entity.get('schemaClass') == 'ReferenceGeneProduct']
    return genes
