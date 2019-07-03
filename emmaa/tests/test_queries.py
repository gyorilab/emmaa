import json
import os
from os.path import abspath, dirname, join
from nose.plugins.attrib import attr
from indra.statements import Phosphorylation, Agent
from emmaa.queries import (Query, PathProperty, get_agent_from_local_grounding,
                           get_agent_from_grounding_service,
                           get_grounding_from_name, get_agent_from_text)


def test_path_property_from_json():
    query_file = join(dirname(abspath(__file__)), 'path_property_query.json')
    with open(query_file, 'r') as f:
        json_dict = json.load(f)
    query = Query._from_json(json_dict)
    assert query
    assert isinstance(query, PathProperty)
    assert isinstance(query.path_stmt, Phosphorylation), query.path_stmt
    assert query.path_stmt.enz.name == 'EGFR', query.path_stmt
    assert query.path_stmt.sub.name == 'ERK', query.path_stmt
    assert isinstance(query.exclude_entities[0], Agent)
    assert query.exclude_entities[0].name == 'PI3K'
    assert isinstance(query.include_entities[0], Agent)
    assert query.include_entities[0].name == 'MAPK1'
    assert set(query.exclude_rels) == set(['IncreaseAmount', 'DecreaseAmount'])
    assert query.include_rels[0] == 'Inhibition'


def test_path_property_to_json():
    stmt = Phosphorylation(enz=Agent('EGFR', db_refs={'HGNC': '3236'}),
                           sub=Agent('ERK', db_refs={'FPLX': 'ERK'}))
    entity_constraints = {'exclude': [Agent('PI3K', db_refs={'FPLX': 'PI3K'})]}
    relationship_contraints = {'exclude': ['IncreaseAmount', 'DecreaseAmount']}
    query = PathProperty(stmt, entity_constraints, relationship_contraints)
    assert query
    json = query.to_json()
    assert json.get('type') == 'path_property'
    path = json.get('path')
    assert path.get('type') == 'Phosphorylation'
    deserialize_query = Query._from_json(json)
    json2 = deserialize_query.to_json()
    assert json == json2, {'json': json, 'json2': json2}


def test_stringify_path_property():
    stmt = Phosphorylation(enz=Agent('EGFR', db_refs={'HGNC': '3236'}),
                           sub=Agent('ERK', db_refs={'FPLX': 'ERK'}))
    entity_constraints = {'exclude': [Agent('PI3K', db_refs={'FPLX': 'PI3K'})]}
    relationship_contraints = {'exclude': ['IncreaseAmount', 'DecreaseAmount']}
    query = PathProperty(stmt, entity_constraints, relationship_contraints)
    query_str = str(query)
    assert query_str == 'PathPropertyQuery(stmt=Phosphorylation(EGFR(), ERK()). Exclude entities: PI3K(). Exclude relations: IncreaseAmount, DecreaseAmount.'


def test_grounding_from_name():
    assert get_grounding_from_name('MAPK1') == ('HGNC', '6871')
    assert get_grounding_from_name('BRAF') == ('HGNC', '1097')


def test_local_grounding():
    agent = get_agent_from_local_grounding('MAPK1')
    assert isinstance(agent, Agent)
    assert agent.name == 'MAPK1'
    assert agent.db_refs == {'HGNC': '6871'}
    # test with lower case
    agent = get_agent_from_local_grounding('mapk1')
    assert isinstance(agent, Agent)
    assert agent.name == 'MAPK1'
    assert agent.db_refs == {'HGNC': '6871'}
    # other agent
    agent = get_agent_from_local_grounding('BRAF')
    assert isinstance(agent, Agent)
    assert agent.name == 'BRAF'
    assert agent.db_refs == {'HGNC': '1097'}


@attr('nonpublic')
def test_grounding_service():
    url = os.environ['GROUNDING_SERVICE_URL']
    agent = get_agent_from_grounding_service('MAPK1', url)
    assert isinstance(agent, Agent)
    assert agent.name == 'MAPK1'
    assert agent.db_refs == {'HGNC': '6871'}
    agent = get_agent_from_local_grounding('BRAF')
    assert isinstance(agent, Agent)
    assert agent.name == 'BRAF'
    assert agent.db_refs == {'HGNC': '1097'}
