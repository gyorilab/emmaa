import datetime
from indra.sources import reach
from indra.literature.s3_client import get_reader_json_str, get_full_text
from indra_reading.scripts.submit_reading_pipeline import \
    submit_reading
from indra_reading.batch.monitor import BatchMonitor
from emmaa.statements import EmmaaStatement


def read_pmid_search_terms(pmid_search_terms):
    """Return extracted EmmaaStatements given a PMID-search term dict.

    Parameters
    ----------
    pmid_search_terms : dict
        A dict representing a set of PMIDs pointing to search terms that
        produced them.

    Returns
    -------
    list[:py:class:`emmaa.model.EmmaaStatement`]
        A list of EmmaaStatements extracted from the given PMIDs.
    """
    pmids = list(pmid_search_terms.keys())
    date = datetime.datetime.utcnow()
    pmid_stmts = read_pmids(pmids, date)
    estmts = []
    for pmid, stmts in pmid_stmts.items():
        for stmt in stmts:
            es = EmmaaStatement(stmt, date, pmid_search_terms[pmid])
            estmts.append(es)
    return estmts


def read_pmids(pmids, date):
    """Return extracted INDRA Statements per PMID after running reading on AWS.

    Parameters
    ----------
    pmids : list[str]
        A list of PMIDs to read.
    date : datetime
        The date and time associated with the reading, typically the
        current time.

    Returns
    -------
    dict[str, list[indra.statements.Statement]
        A dict of PMIDs and the list of Statements extracted for the given
        PMID by reading.
    """
    date_str = date.strftime('%Y-%m-%d-%H-%M-%S')
    pmid_fname = 'pmids-%s.txt' % date_str
    with open(pmid_fname, 'wt') as fh:
        fh.write('\n'.join(pmids))
    job_list = submit_reading('emmaa', pmid_fname, ['reach'])
    monitor = BatchMonitor('run_reach_queue', job_list)
    monitor.watch_and_wait(idle_log_timeout=600,  kill_on_log_timeout=True)
    pmid_stmts = {}
    for pmid in pmids:
        reach_json_str = get_reader_json_str('reach', pmid)
        if reach_json_str is None:
            pmid_stmts[pmid] = []
            continue
        rp = reach.process_json_str(reach_json_str)
        if not rp:
            pmid_stmts[pmid] = []
        else:
            pmid_stmts[pmid] = rp.statements
    return pmid_stmts
