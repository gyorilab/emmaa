from emmaa_service.api import _make_query
from emmaa.queries import PathProperty, DynamicProperty


def test_make_query():
    query, tab = _make_query({
        'typeSelection': 'Activation',
        'subjectSelection': 'BRAF',
        'objectSelection': 'MAPK1'})
    assert isinstance(query, PathProperty)
    assert tab == 'static'
    query, tab = _make_query({
        'agentSelection': 'phosphorylated MAP2K1',
        'valueSelection': 'low',
        'patternSelection': 'always_value'})    
    assert isinstance(query, DynamicProperty)
    assert tab == 'dynamic'
