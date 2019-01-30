__all__ = ['find_latest_s3_file', 'to_emmaa_stmts', 'make_date_str',
           'get_date_from_str']

import os
import boto3
from emmaa.statements import EmmaaStatement
from .date import make_date_str, get_date_from_str


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
