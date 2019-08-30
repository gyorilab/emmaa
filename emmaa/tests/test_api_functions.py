import re

from emmaa.util import RE_DATEFORMAT
from emmaa_service.api import get_model_stats, model_last_updated

MODEL = 'aml'


def test_last_updated():
    key_str = model_last_updated(MODEL)
    assert key_str
    assert re.search(RE_DATEFORMAT, key_str).group()


def test_get_model_statistics():
    model_json = get_model_stats(MODEL)
    assert isinstance(model_json, dict)
