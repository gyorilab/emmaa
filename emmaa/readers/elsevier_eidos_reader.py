import os
import logging
import datetime
from indra.sources import eidos
from indra.literature import elsevier_client
from emmaa.statements import EmmaaStatement


logger = logging.getLogger(__name__)


def read_elsevier_eidos_search_terms(piis_to_terms):
    """Return extracted EmmaaStatements given a dict of PIIS to SearchTerms.

    Parameters
    ----------
    piis_to_terms : dict
        A dict representing a set of PIIs pointing to search terms that
        produced them.

    Returns
    -------
    list[:py:class:`emmaa.model.EmmaaStatement`]
        A list of EmmaaStatements extracted from the given PMIDs.
    """
    piis = list(piis_to_terms.keys())
    date = datetime.datetime.utcnow()
    texts = read_piis(piis)
    pii_stmts = process_texts(texts)
    estmts = []
    for pii, stmts in pii_stmts.items():
        for stmt in stmts:
            for evid in stmt.evidence:
                evid.annotations['pii'] = pii
            es = EmmaaStatement(stmt, date, piis_to_terms[pii])
            estmts.append(es)
    return estmts


def read_piis(piis):
    """Return texts extracted from articles with given PIIs.

    Parameters
    ----------
    piis : list[str]
        A list of PIIs to extract texts from.

    Returns
    -------
    texts : dict
        A dictionary representing PIIs as keys and extracted texts as values.
    """
    texts = {}
    for pii in piis:
        try:
            xml = elsevier_client.download_article(pii, id_type='pii')
            # If we got an empty xml or bad response
            if not xml:
                logger.info('Could not get article content for %s' % pii)
                continue
        # Handle Connection and other errors
        except Exception as e:
            logger.info('Could not get article content for %s because of %s'
                        % (pii, e))
            continue
        try:
            txt = elsevier_client.extract_text(xml)
            # If we could find relevant xml parts
            if not txt:
                logger.info('Could not extract article text for %s' % pii)
                continue
        # Handle Connection and other errors
        except Exception as e:
            logger.info('Could not extract article text for %s because of %s'
                        % (pii, e))
        texts[pii] = txt
    logger.info('Got text back for %d articles.' % len(texts))
    return texts


def process_texts(texts):
    """Process article texts with Eidos and extract INDRA Statements.

    Parameters
    ----------
    texts : dict
        A dictionary mapping PIIs to texts to process.

    Returns
    -------
    pii_stmts : dict
        A dictionary mapping PIIs as keys and extracted INDRA statements.
    """
    eidos_url = os.environ.get('EIDOS_URL')
    logger.info('Reading with Eidos URL: %s' % eidos_url)
    pii_stmts = {}
    for pii, txt in texts.items():
        logger.info('Reading the article with %s pii.' % pii)
        try:
            ep = eidos.process_text(txt, webservice=eidos_url)
            if ep:
                pii_stmts[pii] = ep.statements
        # Handle Connection and other errors
        except Exception as e:
            logger.info('Could not read the text because of %s' % str(e))
            continue
    return pii_stmts
