import os
import re
import boto3
import logging
from datetime import datetime, timedelta
from botocore import UNSIGNED
from botocore.client import Config
from inflection import camelize
from indra.util.aws import get_s3_file_tree, get_date_from_str
from indra.statements import get_all_descendants
from emmaa.subscription import email_bucket

FORMAT = '%Y-%m-%d-%H-%M-%S'
RE_DATETIMEFORMAT = r'\d{4}\-\d{2}\-\d{2}\-\d{2}\-\d{2}\-\d{2}'
RE_DATEFORMAT = r'\d{4}\-\d{2}\-\d{2}'
EMMAA_BUCKET_NAME = 'emmaa'
logger = logging.getLogger(__name__)


def strip_out_date(keystring, date_format='datetime'):
    """Strips out datestring of selected date_format from a keystring"""
    if date_format == 'datetime':
        re_format = RE_DATETIMEFORMAT
    elif date_format == 'date':
        re_format = RE_DATEFORMAT
    try:
        return re.search(re_format, keystring).group()
    except AttributeError:
        logger.warning(f'Can\'t parse string {keystring} for date')
        return None


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


def list_s3_files(bucket, prefix, extension=None):
    client = get_s3_client()
    resp = client.list_objects(Bucket=bucket, Prefix=prefix)
    files = resp.get('Contents', [])
    if extension:
        keys = [file['Key'] for file in files if
                file['Key'].endswith(extension)]
    else:
        keys = [file['Key'] for file in files]
    return keys


def sort_s3_files_by_date_str(bucket, prefix, extension=None):
    """
    Return the list of keys of the files on an S3 path sorted by date starting
    with the most recent one.
    """
    def process_key(key):
        fname_with_extension = os.path.basename(key)
        fname = os.path.splitext(fname_with_extension)[0]
        date_str = fname.split('_')[-1]
        return get_date_from_str(date_str)
    keys = list_s3_files(bucket, prefix, extension=extension)
    keys = sorted(keys, key=lambda k: process_key(k), reverse=True)
    return keys


def sort_s3_files_by_last_mod(bucket, prefix, time_delta=None,
                              extension=None, unsigned=True, reverse=False,
                              w_dt=False):
    """Return a list of s3 objects sorted by their LastModified date on S3
    """
    if time_delta is None:
        time_delta = timedelta()  # zero timedelta
    s3 = get_s3_client(unsigned)
    n_hours_ago = datetime.utcnow() - time_delta
    file_tree = get_s3_file_tree(s3, bucket, prefix,
                                 date_cutoff=n_hours_ago,
                                 with_dt=True)
    key_list = sorted(list(file_tree.get_leaves()), key=lambda t: t[1],
                      reverse=reverse)
    if extension:
        return [t if w_dt else t[0] for t in key_list
                if t[0].endswith(extension)]
    else:
        return key_list if w_dt else [t[0] for t in key_list]


def find_latest_s3_file(bucket, prefix, extension=None):
    """Return the key of the file with latest date string on an S3 path"""
    files = sort_s3_files_by_date_str(bucket, prefix, extension)
    try:
        latest = files[0]
        return latest
    except IndexError:
        logger.debug('File is not found.')


def find_second_latest_s3_file(bucket, prefix, extension=None):
    """Return the key of the file with second latest date string on an S3 path
    """
    files = sort_s3_files_by_date_str(bucket, prefix, extension)
    try:
        latest = files[1]
        return latest
    except IndexError:
        logger.debug("File is not found.")


def find_latest_s3_files(number_of_files, bucket, prefix, extension=None):
    """
    Return the keys of the specified number of files with latest date strings
    on an S3 path sorted by date starting with the earliest one.
    """
    files = sort_s3_files_by_date_str(bucket, prefix, extension)
    keys = []
    for ix in range(number_of_files):
        keys.append(files[ix])
    keys.reverse()
    return keys


def find_number_of_files_on_s3(bucket, prefix, extension=None):
    files = sort_s3_files_by_date_str(bucket, prefix, extension)
    return len(files)


def find_latest_emails(email_type, time_delta=None, w_dt=False):
    """Return a list of keys of the latest emails delivered to s3

    Parameters
    ----------
    email_type : str
        The email type to look for, e.g. 'feedback' if listing bounce and
        complaint emails sent to the ReturnPath address.
    time_delta : datetime.timedelta
        The timedelta to look backwards for listing emails.

    Returns
    -------
    list[Keys]
        A list of keys to the emails of the specified type.
    """
    email_list = sort_s3_files_by_last_mod(email_bucket, email_type,
                                           time_delta, unsigned=False,
                                           w_dt=w_dt)
    ignore = 'AMAZON_SES_SETUP_NOTIFICATION'
    if w_dt:
        return [s for s in email_list if ignore not in s[0]]
    return [s for s in email_list if ignore not in s]


def does_exist(bucket, prefix, extension=None):
    """Check if the file with exact key or starting with prefix and/or with
    extension exist in a bucket.
    """
    all_files = list_s3_files(bucket, prefix, extension)
    if any(fname.startswith(prefix) for fname in all_files):
        return True
    return False


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


def get_class_from_name(cls_name, parent_cls):
    classes = get_all_descendants(parent_cls)
    for cl in classes:
        if cl.__name__.lower() == camelize(cls_name).lower():
            return cl
    raise NotAClassName(f'{cls_name} is not recognized as a '
                        f'{parent_cls.__name__} type!')


class NotAClassName(Exception):
    pass
