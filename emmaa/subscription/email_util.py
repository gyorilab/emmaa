import os
import hmac
import time
import boto3
import hashlib
import logging
from urllib import parse
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

from emmaa.db import get_db
from emmaa.queries import Query
from emmaa.answer_queries import _make_query_str

db = get_db('primary')

logger = logging.getLogger(__name__)

EMAIL_SIGNATURE_KEY = os.environ.get('EMAIL_SIGN')


def __sign_str_concat(email, expiration_str):
    """This is the method to concatenate strings that are to be used in HMAC
    signature generation.

    Email should NOT be url encoded.
    """
    return ' '.join([email, expiration_str])


def generate_unsubscribe_qs(email):
    future = datetime.utcnow() + timedelta(days=7)
    expiration = str(future.timestamp()).split('.')[0]
    signature = generate_signature(email=email, expire_str=expiration)
    return parse.urlencode({'email': email,
                            'expiration': expiration,
                            'signature': signature})


def generate_signature(email, expire_str, digestmod=hashlib.sha256):
    """hmac.new(key, msg=None, digestmod=None)
    Return a new hmac object.
    key is a bytes or bytearray object giving the secret key.
    If msg is present, the method call update(msg) is made.
    digestmod is the digest name, digest constructor or module for the HMAC
    object to use. It supports any name suitable to hashlib.new() and
    defaults to the hashlib.md5 constructor."""
    if not EMAIL_SIGNATURE_KEY:
        logger.error('No secret key set for email signature.'
                     'Cannot generate signature')
        return

    digester = hmac.new(key=EMAIL_SIGNATURE_KEY.encode(encoding='utf-8'),
                        msg=__sign_str_concat(
                            email, expire_str).encode(encoding='utf-8'),
                        digestmod=digestmod)
    return digester.hexdigest()


def verify_email_signature(signature, email, expiration, 
                           digestmod=hashlib.sha256):
    """Verify HMAC signature"""
    if not EMAIL_SIGNATURE_KEY:
        logger.error('No secret key set for email signature. '
                     'Cannot verify signature')
        return False
    actual_digest = hmac.new(
        key=EMAIL_SIGNATURE_KEY.encode(encoding='utf-8'),
        msg=__sign_str_concat(email, expiration).encode(encoding='utf-8'),
        digestmod=digestmod).hexdigest()

    if len(signature) != len(actual_digest):
        return False
    try:
        return hmac.compare_digest(actual_digest, signature)
    except Exception:
        return False


def get_email_subscriptions(email):
    """Verifies which email subsciptions exist for the provided email"""
    user_queries = db.get_subscribed_queries(email)
    if not user_queries:
        return []
    # Todo get the query type from the json
    return [(_make_query_str(Query._from_json(qj)) + f' for model {mid}',
             'Path Query', qh)
            for qj, mid, qh in user_queries]


def register_email_unsubscribe(email, queries):
    """Executes an email unsubscribe request"""
    success = db.update_email_subscription(email, queries, False)
    return success
