import os
import logging
import datetime
from indra.sources import eidos
from indra.literature import elsevier_client
from emmaa.statements import EmmaaStatement


logger = logging.getLogger(__name__)


def read_elsevier_eidos_search_terms(ids_to_terms):
    piis = list(ids_to_terms.keys())
    date = datetime.datetime.utcnow()
    pii_stmts = read_piis(piis)
    estmts = []
    for pii, stmts in pii_stmts.items():
        for stmt in stmts:
            es = EmmaaStatement(stmt, date, ids_to_terms[pii])
            estmts.append(es)
    return estmts


def read_piis(piis):
    eidos_url = os.environ.get('EIDOS_URL')
    logger.info('Reading with Eidos URL: %s' % eidos_url)
    pii_stmts = {}
    for pii in piis:
        pii_stmts[pii] = []
        xml = elsevier_client.download_article(pii, id_type='pii')
        if not xml:
            logger.info('Could not get article content for %s' % pii)
            continue
        txt = elsevier_client.extract_text(xml)
        ep = eidos.process_text(txt, webservice=eidos_url)
        if ep:
            pii_stmts[pii] = ep.statements
    return pii_stmts