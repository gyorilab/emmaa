import os
import hmac
import hashlib
import logging
from urllib import parse
from datetime import datetime, timedelta

from emmaa.db import get_db

db = get_db('primary')

logger = logging.getLogger(__name__)

EMAIL_SIGNATURE_KEY = os.environ.get('EMAIL_SIGN_SECRET')


def __sign_str_concat(email, expiration_str):
    """This is the method to concatenate strings that are to be used in HMAC
    signature generation.

    Email should NOT be url encoded.
    """
    return ' '.join([email, expiration_str])


def generate_unsubscribe_qs(email, days=7):
    """Generate an unsubscribe query string for a url

    Parameters
    ----------
    email : str
        A valid email address
    days : int
        The number of days the query string should be valid. Default: 7.

    Returns
    -------
    str
        A query string of the format 'email=<urlenc
        email>&expiration=<timestamp>&signature=<sha256 hex>'
    """
    if days < 1:
        logger.warning('Expiration date is less than one day into the '
                       'future. Link will likely already be expired.')
    future = datetime.utcnow() + timedelta(days=days)
    expiration = str(future.timestamp()).split('.')[0]
    signature = generate_signature(email=email, expire_str=expiration)
    return parse.urlencode({'email': email,
                            'expiration': expiration,
                            'signature': signature})


def generate_unsubscribe_link(email, days=7, domain='emmaa.indra.bio'):
    """Generate an unsubscribe link for the provided email address

    Given an email address, generate an unsubscribe link using that email
    address. Optionally provide the number of days into the future the link
    should be valid until and the domain name. The domain name is expeceted
    to be of the format "some.domain.com". The appropriate path and prefixes
    will be added together with the query string. Example:

    >>> generate_unsubscribe_link('user@email.com', domain='some.domain.com')
    >>> 'https://some.domain.com/query/unsubscribe?email=user%40email.com' +
        '&expiration=1234567890&signature=1234567890abcdef'

    Parameters
    ----------
    email : str
        An email address.
    days : int
        The number of days into the future the link should be valid until.
        Default: 7.
    domain : str
        A domain name to prefix the query string with. Expected format is:
        "some.domain.com". Default: 'emmaa.indra.bio'

    Returns
    -------
    str
        An unsubscribe link for the provided email and (optionally) domain
    """
    qs = generate_unsubscribe_qs(email, days)
    link = f'https://{domain}/query/unsubscribe?{qs}'
    return link


def generate_signature(email, expire_str, digestmod=hashlib.sha256):
    """Return an HMAC signature based on email and expire_str

    From documentation of HMAC in python:
    key is a bytes or bytearray object giving the secret key.
    If msg is present, the method call update(msg) is made.
    digestmod is the digest name, digest constructor or module for the HMAC
    object to use. It supports any name suitable to hashlib.new().

    Parameters
    ----------
    email : str
        A valid email address. Should not be URL encoded.
    expire_str : str
        A timestamp string in seconds
    digestmod : str|digest constructor|module
        digest name, digest constructor or module for the HMAC object to
        use. Default: hashlib.sha256

    Returns
    -------
    str
        A hexadecimal string representing the signature
    """
    if not EMAIL_SIGNATURE_KEY:
        raise ValueError('No secret key set for email signature. '
                         'Cannot generate signature')

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
    """Verifies which email subsciptions exist for the provided email

    Parameters
    ----------
    email : str
        The email to the check subscriptions for

    Returns
    -------
    list(tuple(str, str, query_hash))
    """
    user_queries = db.get_subscribed_queries(email)
    if not user_queries:
        return []
    return [(qo.to_english() + f' for model {mid}',
             f'{qo.get_type()}'.replace('_', ' '), qh)
            for qo, mid, qh in user_queries]


def register_email_unsubscribe(email, queries):
    """Executes an email unsubscribe request"""
    success = db.update_email_subscription(email, queries, False)
    return success
