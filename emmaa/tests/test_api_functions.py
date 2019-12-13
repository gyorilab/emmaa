import re

from emmaa.util import RE_DATETIMEFORMAT, RE_DATEFORMAT
from emmaa_service.api import get_model_stats, model_last_updated, \
    latest_stats_date

MODEL = 'aml'


def test_last_updated():
    key_str = model_last_updated(MODEL)
    assert key_str
    assert re.search(RE_DATETIMEFORMAT, key_str).group()


def test_latest_stats():
    key_str = latest_stats_date(MODEL)
    assert key_str
    assert re.search(RE_DATEFORMAT, key_str).group()


def test_get_model_statistics():
    date = latest_stats_date(MODEL)
    model_json = get_model_stats(MODEL, date)
    assert isinstance(model_json, dict)
