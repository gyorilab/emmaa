from emmaa_service.api import _make_query
from emmaa.queries import PathProperty


def test_make_query():
    query = _make_query({
        'typeSelection': 'Activation',
        'subjectSelection': 'BRAF',
        'objectSelection': 'MAPK1'})
    assert isinstance(query, PathProperty)
