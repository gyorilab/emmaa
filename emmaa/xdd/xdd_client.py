import os
import requests
from indra_db import get_db


api_key = os.environ.get('XDD_API_KEY')
doc_url = 'https://xdddev.chtc.io/sets/xdd-covid-19/cosmos/api/document'
obj_url = 'https://xdddev.chtc.io/sets/xdd-covid-19/cosmos/api/object/'


def get_document_objects(doi):
    res = requests.get(doc_url, params={'doi': doi, 'api_key': api_key})
    rj = res.json()
    if 'objects' not in rj:
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
    if paper_id_type == 'DOI':
        doi = paper_id

    objects = get_document_objects(doi)
    fig_list = []
    for obj in objects:
        fig_list.append(get_figure(obj))
    return fig_list
