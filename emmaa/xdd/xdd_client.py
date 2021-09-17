import os
import requests
import logging
from indra_db import get_db


logger = logging.getLogger(__name__)
api_key = os.environ.get('XDD_API_KEY')
doc_url = 'https://xdd.wisc.edu/sets/xdd-covid-19/cosmos/api/document'
query_url = 'https://xdd.wisc.edu/sets/xdd-covid-19/cosmos/api/search'


def get_document_objects(doi):
    """Get a list of figure/table object dictionaries for a given DOI."""
    logger.info(f'Got a request to get figures for DOI {doi}')
    # Get first batch of results and find the total number of results
    rj = send_document_search_request(doi, page=0)
    if not rj:
        return []
    total = rj.get('total', 0)
    logger.info(f'Got a total of {total} objects')
    objects = rj['objects']
    page = 0
    while len(objects) < total:
        page += 1
        rj = send_document_search_request(doi, page=page)
        if not rj:
            logger.warning(f'Did not get results for {doi} page {page}')
            break
        objects += rj['objects']
    return objects


def get_document_figures(paper_id, paper_id_type):
    """Get figures and tables from a given paper.

    Parameters
    ----------
    paper_id : str or int
        ID of a paper.
    paper_id_type : str
        A name of a paper ID type (PMID, PMCID, DOI, TRID).

    Returns
    -------
    figures : list[tuple]
        A list of tuples where each tuple is a figure title and bytes content.
    """
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
        logger.warning(f'Could not get DOI from {paper_id_type} {paper_id}, '
                       'returning 0 figures and tables')
        return []
    objects = get_document_objects(doi)
    if not objects:
        return []
    figures = get_figures_from_objects(objects)
    logger.info(f'Returning {len(figures)} figures and tables.')
    return figures


def get_figures_from_query(query, limit=None):
    """Get figures and tables from a query.

    Parameters
    ----------
    query : str
        An entity name or comma-separated entity names to query for.
    limit : int or None
        A number of figures and tables to return.

    Returns
    -------
    figures : list[tuple]
        A list of tuples where each tuple is a link to the paper, a figure
        title and bytes content.
    """
    logger.info(f'Got a request for query {query} with limit {limit}')
    # Get first batch of results and find the total number of results
    rj = send_query_search_request(query, page=0)
    if not rj:
        return []
    total = rj.get('total', 0)
    logger.info(f'Got a total of {total} objects')
    objects = rj['objects']
    page = 0
    # If there's a limit of number of figures so we can stop when we reach it
    # or when we run out of objects
    if limit:
        figures = get_figures_from_objects(objects, True)
        while len(figures) < limit and len(objects) < total:
            page += 1
            rj = send_query_search_request(query, page)
            if not rj:
                logger.warning(f'Did not get results for {query}, page {page}')
                break
            new_figures = get_figures_from_objects(rj['objects'], True)
            figures += new_figures
            objects += rj['objects']
        figures = figures[: limit]
        logger.info(f'Returning {len(figures)} figures and tables.')
        return figures
    # There's no limit so we want to get all objects before getting figures
    while len(objects) < total:
        page += 1
        rj = send_query_search_request(query, page)
        if not rj:
            logger.warning(f'Did not get results for {query} page {page}')
            break
        objects += rj['objects']
    figures = get_figures_from_objects(objects, True)
    logger.info(f'Returning {len(figures)} figures and tables.')
    return figures


def send_request(url, params):
    """Send a request and handle potential errors."""
    try:
        res = requests.get(url, params=params)
    # Catch connection error
    except Exception as e:
        logger.info(e)
        return
    try:
        rj = res.json()
        if 'objects' not in rj:
            params.pop('api_key')
            logger.warning(f'Could not get objects for {params}')
            if 'error' in rj:
                logger.warning(rj['error'])
            return
    # Catch bad response
    except Exception as e:
        logger.info(e)
        return
    return rj


def send_query_search_request(query, page):
    """Send a request to get one page of results for a query."""
    logger.info(f'Sending a request for query {query}, page {page}')
    return send_request(
        query_url,
        {'query': query, 'inclusive': True, 'page': page, 'api_key': api_key})


def send_document_search_request(doi, page):
    """Send a request to get one page of results for a DOI."""
    logger.info(f'Sending a request for DOI {doi}, page {page}')
    return send_request(doc_url,
                        {'doi': doi, 'api_key': api_key, 'page': page})


def get_figures_from_objects(objects, paper_links=False):
    """Get a list of paper links, figure titles and their content bytes from
    a list of object dictionaries (returned from query or document api)."""
    figures = []
    for obj in objects:
        for child in obj['children']:
            if child['cls'] in ['Figure', 'Table']:
                txt = child['header_content']
                b = child['bytes']
                if paper_links:
                    urls = set()
                    for link in obj['bibjson']['link']:
                        urls.add(link['url'])
                    figures.append((urls, txt, b))
                else:
                    figures.append((txt, b))
    return figures
