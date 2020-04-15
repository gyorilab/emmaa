import json
from os.path import abspath, dirname, join
from indra.statements import Phosphorylation, Agent, ModCondition
from emmaa.queries import Query, PathProperty, DynamicProperty, \
    get_agent_from_text, get_agent_from_trips


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


def test_path_property_to_english():
    stmt = Phosphorylation(enz=Agent('EGFR', db_refs={'HGNC': '3236'}),
                           sub=Agent('ERK', db_refs={'FPLX': 'ERK'}))
    query = PathProperty(stmt)
    engl = query.to_english()
    assert engl == 'EGFR phosphorylates ERK.'


def test_dynamic_property_from_json():
    query_file = join(dirname(abspath(__file__)), 'dynamic_property_query.json')
    with open(query_file, 'r') as f:
        json_dict = json.load(f)
    query = Query._from_json(json_dict)
    assert query
    assert isinstance(query, DynamicProperty)
    assert isinstance(query.entity, Agent)
    assert query.entity.name == 'EGFR'
    assert isinstance(query.pattern_type, str)
    assert query.pattern_type == 'always_value'
    assert isinstance(query.quant_value, str)
    assert query.quant_value == 'low'
    assert isinstance(query.quant_type, str)
    assert query.quant_type == 'qualitative'


def test_dynamic_property_to_json():
    agent = Agent('EGFR', mods=[ModCondition('phosphorylation')],
                  db_refs={'HGNC': '3236'})
    query = DynamicProperty(agent, 'always_value', 'low', 'qualitative')
    json = query.to_json()
    assert json.get('type') == 'dynamic_property'
    entity = json.get('entity')
    assert entity.get('name') == 'EGFR'
    assert entity.get('db_refs') == {"HGNC": "3236"}
    assert json.get('pattern_type') == 'always_value'
    quantity = json.get('quantity')
    assert quantity.get('type') == 'qualitative'
    assert quantity.get('value') == 'low'


def test_stringify_dynamic_property():
    agent = Agent('EGFR', mods=[ModCondition('phosphorylation')],
                  db_refs={'HGNC': '3236'})
    query = DynamicProperty(agent, 'always_value', 'low', 'qualitative')
    query_str = str(query)
    assert query_str == ("DynamicPropertyQuery(entity=EGFR(mods: "
                         "(phosphorylation)), pattern=always_value, "
                         "molecular quantity=('qualitative', 'low'))")


def test_dynamic_property_to_english():
    agent = Agent('EGFR', mods=[ModCondition('phosphorylation')],
                  db_refs={'HGNC': '3236'})
    query = DynamicProperty(agent, 'always_value', 'low', 'qualitative')
    assert query.to_english() == 'Phosphorylated EGFR is always low.'
    query.pattern_type = 'eventual_value'
    assert query.to_english() == 'Phosphorylated EGFR is eventually low.'


def test_grounding():
    agent = get_agent_from_text('MAPK1')
    assert isinstance(agent, Agent)
    assert agent.name == 'MAPK1'
    assert agent.db_refs == {'TEXT': 'MAPK1',
                             'HGNC': '6871', 'UP': 'P28482'}, agent.db_refs
    # test with lower case
    agent = get_agent_from_text('mapk1')
    assert isinstance(agent, Agent)
    assert agent.name == 'MAPK1'
    assert agent.db_refs == {'TEXT': 'mapk1',
                             'HGNC': '6871', 'UP': 'P28482'}, agent.db_refs
    # other agent
    agent = get_agent_from_text('BRAF')
    assert isinstance(agent, Agent)
    assert agent.name == 'BRAF'
    assert agent.db_refs == {'TEXT': 'BRAF',
                             'HGNC': '1097', 'UP': 'P15056'}, agent.db_refs


def test_agent_from_trips():
    ag = get_agent_from_trips('MAP2K1')
    assert isinstance(ag, Agent)
    assert ag.name == 'MAP2K1'
    assert not ag.mods
    ag_phos = get_agent_from_trips('phosphorylated MAP2K1')
    assert ag_phos.mods
