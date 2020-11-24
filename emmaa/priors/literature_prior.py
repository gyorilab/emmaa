import tqdm
import logging
import datetime
from indra.util import batch_iter
from indra_db import get_db
from indra_db.util import distill_stmts
from indra_db.client.principal import get_raw_stmt_jsons_from_papers
from indra.literature import pubmed_client
from indra.statements import stmts_from_json
from emmaa.statements import EmmaaStatement


logger = logging.getLogger(__name__)


def get_pmids(search_terms=None, mesh_ids=None):
    """Return a set of PMIDs based on search terms and/or MeSH IDs.

    Parameters
    ----------
    search_terms : list of str or None
        Any number of string search terms to find PMIDs.
    mesh_ids : list of str or None
        Any number of MeSH IDs to find PMIDs.

    Returns
    -------
    set of str
        A set of PMIDs found using the given search terms and/or MeSH
        IDs.
    """
    search_terms = [] if not search_terms else search_terms
    mesh_ids = [] if not mesh_ids else mesh_ids
    all_ids = set()
    for term in search_terms:
        all_ids |= set(pubmed_client.get_ids(term))
    for mesh_id in mesh_ids:
        all_ids |= set(pubmed_client.get_ids_for_mesh(mesh_id))
    return all_ids


def get_raw_statements_for_pmids(pmids, mode='all', batch_size=100):
    """Return EmmaaStatements based on extractions from given PMIDs.

    Paramters
    ---------
    pmids : set or list of str
        A set of PMIDs to find raw INDRA Statements for in the INDRA DB.
    mode : 'all' or 'distilled'
        The 'distilled' mode makes sure that the "best", non-redundant
        set of raw statements are found across potentially redundant text
        contents and reader versions. The 'all' mode doesn't do such
        distillation but is significantly faster.
    batch_size : Optional[int]
        Determines how many PMIDs to fetch statements for in each
        iteration. Default: 100.

    Returns
    -------
    list of emmaa.statement.Statement
        A list of EMMAA Statements that wrap the obtained raw INDRA
        Statements.
    """
    db = get_db('primary')
    print(f'Getting raw statements for {len(pmids)} PMIDs')
    estmts = []
    timestamp = datetime.datetime.now()
    for pmid_batch in tqdm.tqdm(batch_iter(pmids, return_func=set,
                                           batch_size=batch_size),
                                total=len(pmids)/batch_size):
        if mode == 'distilled':
            clauses = [
                db.TextRef.pmid.in_(pmid_batch),
                db.TextContent.text_ref_id == db.TextRef.id,
                db.Reading.text_content_id == db.TextContent.id,
                db.RawStatements.reading_id == db.Reading.id]
            distilled_stmts = distill_stmts(db, get_full_stmts=True,
                                            clauses=clauses)
            estmts += [EmmaaStatement(stmt, timestamp, [])
                       for stmt in distilled_stmts]
        else:
            id_stmts = \
                get_raw_stmt_jsons_from_papers(pmid_batch, id_type='pmid',
                                               db=db)
            estmts = []
            for _id, stmt_jsons in id_stmts.items():
                stmts = stmts_from_json(stmt_jsons)
                estmts += [EmmaaStatement(stmt, timestamp, [])
                           for stmt in stmts]
    return estmts
