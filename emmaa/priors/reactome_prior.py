import requests
from functools import lru_cache

@lru_cache(10000)
def rx_id_from_up_id(up_id):
    """Get the Reactome Stable ID for a given Uniprot ID."""
    react_search_url = 'http://www.reactome.org/ContentService/search/query'
    params = {'query': up_id, 'cluster': 'true', 'species':'Homo sapiens'}
    headers = {'Accept': 'application/json'}
    res = requests.get(react_search_url, headers=headers, params=params)
    if not res.status_code == 200:
        return None
    json = res.json()
    results = json.get('results')
    if not results:
        print('No results for %s' % up_id)
        return None
    stable_ids = []
    for result in results:
        entries = result.get('entries')
        for entry in entries:
            stable_id = entry.get('stId')
            if not stable_id:
                continue
            name = entry.get('name')
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

