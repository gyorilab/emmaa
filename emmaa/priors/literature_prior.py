import tqdm
from indra_db import get_db
from indra_db.util import distill_stmts
from indra.util import batch_iter
from indra.literature import pubmed_client
from indra.statements import stmts_to_json_file


def get_pmids(search_terms=None, mesh_ids=None):
    search_terms = [] if not search_terms else search_terms
    mesh_ids = [] if not mesh_ids else mesh_ids
    all_ids = set()
    for term in search_terms:
        all_ids |= set(pubmed_client.get_ids(term))
    for mesh_id in mesh_ids:
        all_ids |= set(pubmed_client.get_ids_for_mesh(mesh_id))
    return all_ids


def get_raw_statements_for_pmdis(pmids, batch_size=100):
    db = get_db('primary')
    print(f'Getting raw statements for {len(pmids)} PMIDs')
    all_stmts = []
    for pmid_batch in tqdm.tqdm(batch_iter(pmids, return_func=set,
                                           batch_size=batch_size)):
        clauses = [
            db.TextRef.pmid.in_(pmid_batch),
            db.TextContent.text_ref_id == db.TextRef.id,
            db.Reading.text_content_id == db.TextContent.id,
            db.RawStatements.reading_id == db.Reading.id]
        all_stmts += distill_stmts(db, get_full_stmts=True, clauses=clauses)
    return all_stmts