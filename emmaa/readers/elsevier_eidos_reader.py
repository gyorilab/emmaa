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
    texts = read_piis(piis)
    pii_stmts = process_texts(texts)
    estmts = []
    for pii, stmts in pii_stmts.items():
        for stmt in stmts:
            es = EmmaaStatement(stmt, date, ids_to_terms[pii])
            estmts.append(es)
    return estmts


def read_piis(piis):
    texts = {}
    for pii in piis:
        try:
            xml = elsevier_client.download_article(pii, id_type='pii')
            if not xml:
                logger.info('Could not get article content for %s' % pii)
                continue
        except Exception as e:
            logger.info('Could not get article content for %s because of %s'
                        % (pii, e))
            continue
        try:
            txt = elsevier_client.extract_text(xml)
            if not txt:
                logger.info('Could not extract article text for %s' % pii)
                continue
        except Exception as e:
            logger.info('Could not extract article text for %s because of %s'
                        % (pii, e))
        texts[pii] = txt
    logger.info('Got text back for %d articles.' % len(texts))
    return texts


def process_texts(texts):
    eidos_url = os.environ.get('EIDOS_URL')
    logger.info('Reading with Eidos URL: %s' % eidos_url)
    pii_stmts = {}
    for pii, txt in texts.items():
        logger.info('Reading the article with %s pii.' % pii)
        try:
            ep = eidos.process_text(txt, webservice=eidos_url)
            if ep:
                pii_stmts[pii] = ep.statements
        except Exception as e:
            logger.info('Could not read the text because of %s' % str(e))
            continue
    return pii_stmts
