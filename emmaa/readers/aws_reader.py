import boto3
import datetime
from indra.sources import reach
from indra.literature.s3_client import get_reader_json_str, get_full_text
from indra.tools.reading.submit_reading_pipeline import \
    submit_reading, wait_for_complete

client = boto3.client('batch')
date_str = datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')


def read_pmids(pmids):
    """Return extracted INDRA Statements per PMID after running reading on AWS.

    Parameters
    ----------
    pmids : list[str]
        A list of PMIDs to read.

    Returns
    -------
    dict[str, list[indra.statements.Statement]]
        A dict of PMIDs and the list of Statements extracted for the given
        PMID by reading.
    """
    pmid_fname = 'pmids-%s.txt' % date_str
    with open(pmid_fname, 'wt') as fh:
        fh.write('\n'.join(pmids))
    job_list = submit_reading('emmaa', pmid_fname, ['reach'])
    wait_for_complete('run_reach_queue', job_list, idle_log_timeout=600,
                      kill_on_log_timeout=True)
    pmid_stmts = {}
    for pmid in pmids:
        reach_json_str = get_reader_json_str('reach', pmid)
        rp = reach.process_json_str(reach_json_str)
        if not rp:
            pmid_stmts[pmid] = []
        else:
            pmid_stmts[pmid] = rp.statements
    return pmid_stmts
