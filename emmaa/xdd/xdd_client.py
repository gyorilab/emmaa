import os
import requests
import logging
from indra_db import get_db


logger = logging.getLogger()
api_key = os.environ.get('XDD_API_KEY')
doc_url = 'https://xdddev.chtc.io/sets/xdd-covid-19/cosmos/api/document'
obj_url = 'https://xdddev.chtc.io/sets/xdd-covid-19/cosmos/api/object/'
query_url = 'https://xdd.wisc.edu/sets/xdd-covid-19/cosmos/api/search'


def get_document_objects(doi):
    res = requests.get(doc_url, params={'doi': doi, 'api_key': api_key})
    rj = res.json()
    if 'objects' not in rj:
        logger.warning(f'Could not get objects for {doi}')
        if 'error' in rj:
            logger.warning(rj['error'])
        return
    objects = [
        obj for obj in rj['objects'] if obj['cls'] in ['Figure', 'Table']]
    return objects


def get_figure(obj_dict):
    txt = obj_dict['header_content']
    url = f"{obj_url}{obj_dict['id']}"
    res = requests.get(url, {'api_key': api_key})
    rj = res.json()
    if 'objects' not in rj:
        return txt, None
    b = rj['objects'][0]['children'][0]['bytes']
    return txt, b


def get_document_figures(paper_id, paper_id_type):
    paper_id_type = paper_id_type.upper()
    if paper_id_type == 'DOI':
        doi = paper_id
    else:
        db = get_db('primary')
        if paper_id_type == 'TRID':
            tr = db.select_one(db.TextRef, db.TextRef.id == paper_id)
        elif paper_id_type == 'PMID':
            tr = db.select_one(db.TextRef, db.TextRef.pmid == paper_id)
        elif paper_id_type == 'PMCID':
            tr = db.select_one(db.TextRef, db.TextRef.pmcid == paper_id)
        ref_dict = tr.get_ref_dict()
        doi = ref_dict.get('DOI')
    if not doi:
        return []
    objects = get_document_objects(doi)
    if not objects:
        return []
    fig_list = []
    for obj in objects:
        fig_list.append(get_figure(obj))
    return fig_list


def get_search_figures(query):
    res = requests.get(query_url, params={'query': query, 'api_key': api_key})
    rj = res.json()
    if 'objects' not in rj:
        logger.warning(f'Could not get objects for {query}')
        if 'error' in rj:
            logger.warning(rj['error'])
        return
    figures = []
    for obj in rj['objects']:
        for child in obj['children']:
            if child['cls'] in ['Figure', 'Table']:
                txt = child['header_content']
                b = child['bytes']
                figures.append((txt, b))
    return figures
