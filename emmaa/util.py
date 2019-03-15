import os
import boto3
import logging
from datetime import datetime
from botocore import UNSIGNED
from botocore.client import Config


FORMAT = '%Y-%m-%d-%H-%M-%S'
logger = logging.getLogger(__name__)


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


def sort_s3_files_by_date(bucket, prefix, extension=None):
    """
    Return the list of keys of the files on an S3 path sorted by date starting
    with the most recent one.
    """
    def process_key(key):
        fname_with_extension = os.path.basename(key)
        fname = os.path.splitext(fname_with_extension)[0]
        date_str = fname.split('_')[1]
        return get_date_from_str(date_str)
    client = get_s3_client()
    resp = client.list_objects(Bucket=bucket, Prefix=prefix)
    files = resp.get('Contents', [])
    if extension:
        files = [file for file in files if file['Key'].endswith(extension)]
    files = sorted(files, key=lambda f: process_key(f['Key']), reverse=True)
    return files


def find_latest_s3_file(bucket, prefix, extension=None):
    """Return the key of the file with latest date string on an S3 path"""
    files = sort_s3_files_by_date(bucket, prefix, extension)
    try:
        latest = files[0]['Key']
        return latest
    except IndexError:
        logger.info('File is not found.')


def find_second_latest_s3_file(bucket, prefix, extension=None):
    """Return the key of the file with second latest date string on an S3 path"""
    files = sort_s3_files_by_date(bucket, prefix, extension)
    try:
        latest = files[1]['Key']
        return latest
    except IndexError:
        logger.info("File is not found.")


def find_latest_s3_files(number_of_files, bucket, prefix, extension=None):
    """
    Return the keys of the specified number of files with latest date strings
    on an S3 path sorted by date starting with the earliest one.
    """
    files = sort_s3_files_by_date(bucket, prefix, extension)
    keys = []
    for ix in range(number_of_files):
        keys.append(files[ix]['Key'])
    keys.reverse()
    return keys


def find_number_of_files_on_s3(bucket, prefix, extension=None):
    files = sort_s3_files_by_date(bucket, prefix, extension)
    return len(files)


def get_s3_client(unsigned=True):
    """Return a boto3 S3 client with optional unsigned config.

    Parameters
    ----------
    unsigned : Optional[bool]
        If True, the client will be using unsigned mode in which public
        resources can be accessed without credentials. Default: True

    Returns
    -------
    botocore.client.S3
        A client object to AWS S3.
    """
    if unsigned:
        return boto3.client('s3', config=Config(signature_version=UNSIGNED))
    else:
        return boto3.client('s3')
