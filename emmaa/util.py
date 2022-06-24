import os
import re
from typing import Dict, Any
import boto3
import logging
import json
import pickle
import zlib
import tweepy
from flask import Flask
from pathlib import Path
from datetime import datetime, timedelta
from botocore import UNSIGNED
from botocore.client import Config, ClientError
from inflection import camelize
from zipfile import ZipFile
from indra.util.aws import get_s3_file_tree, get_date_from_str, iter_s3_keys
from indra.statements import get_all_descendants
from indra.literature.s3_client import gzip_string
from emmaa.subscription.email_service import email_bucket

FORMAT = '%Y-%m-%d-%H-%M-%S'
RE_DATETIMEFORMAT = r'\d{4}\-\d{2}\-\d{2}\-\d{2}\-\d{2}\-\d{2}'
RE_DATEFORMAT = r'\d{4}\-\d{2}\-\d{2}'
EMMAA_BUCKET_NAME = 'emmaa'
logger = logging.getLogger(__name__)


FORMATTED_TYPE_NAMES = {'pysb': 'PySB',
                        'pybel': 'PyBEL',
                        'signed_graph': 'Signed Graph',
                        'unsigned_graph': 'Unsigned Graph'}


TWITTER_MODEL_TYPES = {'pysb': '@PySysBio',
                       'pybel': '@pybelbio',
                       'signed_graph': 'Signed Graph',
                       'unsigned_graph': 'Unsigned Graph'}


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
    files = iter_s3_keys(client, bucket, prefix)
    if extension:
        keys = [f for f in files if f.endswith(extension)]
    else:
        keys = list(files)
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
    if len(keys) < 2:
        return keys
    keys = sorted(keys, key=lambda k: process_key(k), reverse=True)
    return keys


def sort_s3_files_by_last_mod(bucket, prefix, time_delta=None,
                              extension=None, unsigned=True, reverse=False,
                              w_dt=False):
    """Return a list of s3 object keys sorted by their LastModified date on S3

    Parameters
    ----------
    bucket : str
        s3 bucket to look for keys in
    prefix : str
        The prefix to use for the s3 keys
    time_delta : Optional[datetime.timedelta]
        If used, should specify how far back the to look for files on s3.
        Default: None
    extension : Optional[str]
        If used, limit keys to those with the matching file extension.
        Default: None.
    unsigned : bool
        If True, use unsigned s3 client. Default: True.
    reverse : bool
        Reverse the sort order of the returned s3 files. Default: False.
    w_dt : bool
        If True, return list with datetime object along with key as tuple
        (key, datetime.datetime). Default: False.

    Returns
    -------
    list
        A list of s3 keys. If w_dt is True, each item is a tuple of
        (key, datetime.datetime) of the LastModified date.
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


def find_nth_latest_s3_file(n, bucket, prefix, extension=None):
    """Return the key of the file with nth (0-indexed) latest date string on
    an S3 path"""
    files = sort_s3_files_by_date_str(bucket, prefix, extension)
    try:
        latest = files[n]
        return latest
    except IndexError:
        logger.debug('File is not found.')


def find_latest_s3_file(bucket, prefix, extension=None):
    """Return the key of the file with latest date string on an S3 path"""
    return find_nth_latest_s3_file(0, bucket, prefix, extension)


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
    w_dt : bool
        If True, return a list of (key, datetime.datetime) tuples.

    Returns
    -------
    list[Keys]
        A list of keys to the emails of the specified type. If w_dt is True,
        each item is a tuple of (key, datetime.datetime) of the LastModified
        date.
    """
    email_list = sort_s3_files_by_last_mod(email_bucket, email_type,
                                           time_delta, unsigned=False,
                                           w_dt=w_dt)
    ignore = 'AMAZON_SES_SETUP_NOTIFICATION'
    if w_dt:
        return [s for s in email_list if ignore not in s[0]]
    return [s for s in email_list if ignore not in s]


def get_email_content(key):
    s3 = get_s3_client(unsigned=False)
    email_obj = s3.get_object(Bucket=email_bucket, Key=key)
    return email_obj['Body'].read().decode()


def find_index_of_s3_file(key, bucket, prefix, extension=None):
    files = sort_s3_files_by_date_str(bucket, prefix, extension)
    ix = files.index(key)
    return ix


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


def _get_flask_app():
    emmaa_service_dir = Path(__file__).parent.parent.joinpath(
        'emmaa_service', 'templates')
    app = Flask('Static app', template_folder=emmaa_service_dir.as_posix())
    return app


def load_pickle_from_s3(bucket, key):
    client = get_s3_client()
    try:
        logger.info(f'Loading object from {key}')
        obj = client.get_object(Bucket=bucket, Key=key)
        content = pickle.loads(obj['Body'].read())
        return content
    except OverflowError:
        logger.info(f'Downloading file')
        client.download_file(bucket, key, 'temp.pkl')
        with open('temp.pkl', 'rb') as f:
            content = pickle.load(f)
        return content
    except Exception as e:
        logger.info(f'Could not load the pickle from {key}')
        logger.info(e)


def save_pickle_to_s3(obj, bucket, key, intelligent_tiering=True):
    logger.info('Pickling object')
    obj_str = pickle.dumps(obj, protocol=4)
    logger.info(f'Saving object to {key}')
    s3_put(bucket=bucket, key=key, body=obj_str, unsigned_client=False,
           intelligent_tiering=intelligent_tiering)


def load_json_from_s3(bucket, key):
    client = get_s3_client()
    logger.info(f'Loading object from {key}')
    obj = client.get_object(Bucket=bucket, Key=key)
    content = json.loads(obj['Body'].read().decode('utf8'))
    return content


def save_json_to_s3(obj, bucket, key, save_format='json',
                    intelligent_tiering=True):
    json_str = _get_json_str(obj, save_format=save_format)
    logger.info(f'Uploading the {save_format} object to S3')
    s3_put(bucket=bucket, key=key, body=json_str.encode('utf8'),
           unsigned_client=False, intelligent_tiering=intelligent_tiering)


def load_gzip_json_from_s3(bucket, key):
    client = get_s3_client()
    # Newer files are zipped with gzip while older with zipfile
    try:
        logger.info(f'Loading zipped object from {key}')
        gz_obj = client.get_object(Bucket=bucket, Key=key)
        content = json.loads(zlib.decompress(
            gz_obj['Body'].read(), 16+zlib.MAX_WBITS).decode('utf8'))
    except Exception as e:
        logger.info(e)
        logger.info('Could not load with gzip, using zipfile')
        logger.info(f'Loading zipfile from {key}')
        client.download_file(bucket, key, 'temp.zip')
        with ZipFile('temp.zip', 'r') as zipf:
            content = json.loads(zipf.read(zipf.namelist()[0]))
    return content


def save_gzip_json_to_s3(obj, bucket, key, save_format='json',
                         intelligent_tiering=True):
    json_str = _get_json_str(obj, save_format=save_format)
    gz_str = gzip_string(json_str, f'assembled_stmts.{save_format}')
    s3_put(bucket=bucket, key=key, body=gz_str, unsigned_client=False,
           intelligent_tiering=intelligent_tiering)


def _get_json_str(json_obj, save_format='json'):
    logger.info(f'Dumping the {save_format} into a string')
    if save_format == 'json':
        json_str = json.dumps(json_obj, indent=1)
    elif save_format == 'jsonl':
        json_str = '\n'.join(
            [json.dumps(item) for item in json_obj])
    return json_str


class NotAClassName(Exception):
    pass


def get_credentials(key):
    client = boto3.client('ssm')
    auth_dict = {}
    for par in ['consumer_token', 'consumer_secret', 'access_token',
                'access_secret']:
        name = f'/twitter/{key}/{par}'
        try:
            response = client.get_parameter(Name=name, WithDecryption=True)
            val = response['Parameter']['Value']
            auth_dict[par] = val
        except Exception as e:
            print(e)
            break
    return auth_dict


def get_oauth_dict(auth_dict):
    oauth = tweepy.OAuthHandler(auth_dict.get('consumer_token'),
                                auth_dict.get('consumer_secret'))
    oauth.set_access_token(auth_dict.get('access_token'),
                           auth_dict.get('access_secret'))
    return oauth


def update_status(msg, twitter_cred):
    twitter_auth = get_oauth_dict(twitter_cred)
    if twitter_auth is None:
        return
    twitter_api = tweepy.API(twitter_auth)
    twitter_api.update_status(msg)


def _make_delta_msg(model_name, msg_type, delta, date, mc_type=None,
                    test_corpus=None, test_name=None, new_papers=None,
                    is_tweet=False):
    if is_tweet:
        model_type_dict = TWITTER_MODEL_TYPES
    else:
        model_type_dict = FORMATTED_TYPE_NAMES
    if len(delta['added']) == 0:
        logger.info(f'No {msg_type} delta found')
        return
    if not test_name:
        test_name = test_corpus
    plural = 's' if len(delta['added']) > 1 else ''
    if msg_type == 'stmts':
        if not new_papers:
            logger.info(f'No new papers found')
            return
        else:
            paper_plural = 's' if new_papers > 1 else ''
            url = (f'https://emmaa.indra.bio/dashboard/{model_name}'
                   f'?tab=model&date={date}#addedStmts')
            start = (f'Today I read {new_papers} new publication{paper_plural}'
                     ' and learned ')
            delta_part = f'{len(delta["added"])} new mechanism{plural}'
            middle = ''
    elif msg_type == 'applied_tests':
        url = (f'https://emmaa.indra.bio/dashboard/{model_name}?tab=tests'
               f'&test_corpus={test_corpus}&date={date}#newAppliedTests')
        start = 'Today I applied '
        delta_part = f'{len(delta["added"])} new test{plural}'
        middle = f' in the {test_name}'
    elif msg_type == 'passed_tests' and mc_type:
        url = (f'https://emmaa.indra.bio/dashboard/{model_name}?tab=tests'
               f'&test_corpus={test_corpus}&date={date}#newPassedTests')
        start = 'Today I explained '
        delta_part = f'{len(delta["added"])} new observation{plural}'
        middle = (f' in the {test_name} with my {model_type_dict[mc_type]} '
                  'model')
    else:
        raise TypeError(f'Invalid message type: {msg_type}.')
    msg = f'{start}{delta_part}{middle}. See {url} for more details.'
    return {'url': url, 'start': start, 'delta_part': delta_part,
            'middle': middle, 'message': msg}


def s3_put(
    bucket: str,
    key: str,
    body: bytes,
    unsigned_client: bool,
    intelligent_tiering: bool = False,
    **s3_options
):
    """A wrapper around boto3's put_object method.

    Parameters
    ----------
    bucket :
        The S3 bucket to put the object in.
    key :
        The key to put the object in.
    body :
        The bytestring representation of an object to put in a body as a
        bytestring.
    unsigned_client :
        Whether to use an unsigned client.
    intelligent_tiering :
        Whether to use intelligent tiering. Default is False.
    s3_options :
        Additional options to pass to the put_object method. If there are
        any duplicate keys, the explicit values set in the parameters will
        override the values set in the s3_options.
    """
    client = get_s3_client(unsigned=unsigned_client)
    options = {**s3_options, **{'Body': body, 'Bucket': bucket, 'Key': key}}
    if intelligent_tiering:
        options['StorageClass'] = 'INTELLIGENT_TIERING'
    client.put_object(**options)


def s3_head_object(bucket: str, key: str, unsigned_client: bool = False) -> \
        Dict[str, Any]:
    client = get_s3_client(unsigned=unsigned_client)
    try:
        return client.head_object(Bucket=bucket, Key=key)
    except ClientError as err:
        if err.response['Error']['Code'] == 'NoSuchKey':
            logger.error(f'key {key} not in S3')
            raise KeyError(key) from err
        else:
            logger.error(err)
            logger.error(
                f'Error checking object {key} from bucket {bucket} with s3.head_object'
            )
            raise err


def get_s3_object_archive_status(bucket, key, unsigned_client=False) -> Dict[str, bool]:
    # See more details about the HeadObject status response here:
    # https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html
    head_resp = s3_head_object(bucket=bucket, key=key,
                               unsigned_client=unsigned_client)

    is_in_intelligent_tiering = False
    is_archived = False

    if head_resp:
        try:
            # Look 'ResponseMetadata' -> 'HTTPHeaders' -> 'x-amz-archive-status'
            is_in_intelligent_tiering = \
                head_resp['ResponseMetadata']['HTTPHeaders']['x-amz-storage-class'] == 'INTELLIGENT_TIERING'
        except KeyError:
            pass
        if is_in_intelligent_tiering:
            # Find 'ResponseMetadata' -> 'HTTPHeaders' -> 'x-amz-storage-class'
            # Options are: ARCHIVE_ACCESS | DEEP_ARCHIVE_ACCESS
            try:
                archive_status = head_resp['ResponseMetadata']['HTTPHeaders']['x-amz-archive-status']
                is_archived = \
                    'ARCHIVE_ACCESS' == archive_status or \
                    'DEEP_ARCHIVE_ACCESS' == archive_status
            except KeyError:
                pass

    return {'intelligent_tiering': is_in_intelligent_tiering,
            'archived': is_archived}
