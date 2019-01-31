import os
import boto3
from datetime import datetime
from emmaa.statements import EmmaaStatement


FORMAT = '%Y-%m-%d-%H-%M-%S'


def get_date_from_str(date_str):
    return datetime.strptime(date_str, FORMAT)


def make_date_str(date=None):
    """Return a date string in a standardized format.

    Parameters
    ----------
    date : Optional[datetime.datetime]
        A date object to get the standardized string for. If not provided,
        utcnow() is used to construct the date. (Note: using UTC is important
        because this code may run in multiple contexts).

    Returns
    -------
    str
        The datetime string in a standardized format.
    """
    if not date:
        date = datetime.utcnow()
    return date.strftime(FORMAT)


def find_latest_s3_file(bucket, prefix):
    """Return the key of the file with latest date string on an S3 path"""
    def process_key(key):
        fname_with_extension = os.path.basename(key)
        fname = os.path.splitext(fname_with_extension)[0]
        date_str = fname.split('_')[1]
        return get_date_from_str(date_str)
    client = boto3.client('s3')
    resp = client.list_objects(Bucket=bucket, Prefix=prefix)
    files = resp.get('Contents', [])
    files = sorted(files, key=lambda f: process_key(f['Key']), reverse=True)
    latest = files[0]['Key']
    return latest


def to_emmaa_stmts(stmt_list, date, search_terms):
    """Make EMMAA statements from INDRA Statements with the given metadata."""
    emmaa_stmts = []
    for indra_stmt in stmt_list:
        es = EmmaaStatement(indra_stmt, date, search_terms)
        emmaa_stmts.append(es)
    return emmaa_stmts
