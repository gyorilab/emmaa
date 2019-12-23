from nose.plugins.attrib import attr
from emmaa_service.api import _get_model_meta_data, get_model_config,\
    _make_query
from emmaa.queries import PathProperty


@attr('nonpublic')
def test_get_metadata():
    metadata = _get_model_meta_data()
    assert len(metadata) == 11, len(metadata)
    assert len(metadata[0]) == 3
    assert isinstance(metadata[0][0], str)
    assert isinstance(metadata[0][1], dict)
    assert isinstance(metadata[0][2], str)


@attr('nonpublic')
def test_get_model_config():
    config = get_model_config('aml')
    assert config
    assert isinstance(config, dict)
    # can't get if there's no human readable name
    config = get_model_config('test')
    assert not config


def test_make_query():
    query = _make_query({
        'typeSelection': 'Activation',
        'subjectSelection': 'BRAF',
        'objectSelection': 'MAPK1'})
    assert isinstance(query, PathProperty)
