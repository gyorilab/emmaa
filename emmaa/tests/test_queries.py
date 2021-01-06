import json
from os.path import abspath, dirname, join
from indra.statements import Phosphorylation, Agent, ModCondition, Inhibition
from emmaa.queries import Query, PathProperty, DynamicProperty, \
    OpenSearchQuery, get_agent_from_text, get_agent_from_trips, \
    get_agent_from_gilda


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
    assert query_str == (
        'PathPropertyQuery(stmt=Phosphorylation(EGFR(), ERK()). Exclude '
        'entities: PI3K(). Exclude relations: IncreaseAmount, DecreaseAmount.')


def test_path_property_to_english():
    stmt = Phosphorylation(enz=Agent('EGFR', db_refs={'HGNC': '3236'}),
                           sub=Agent('ERK', db_refs={'FPLX': 'ERK'}))
    query = PathProperty(stmt)
    engl = query.to_english()
    assert engl == 'EGFR phosphorylates ERK.'


def test_dynamic_property_from_json():
    query_file = join(
        dirname(abspath(__file__)), 'dynamic_property_query.json')
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


def test_open_query_from_json():
    query_file = join(dirname(abspath(__file__)), 'open_query.json')
    with open(query_file, 'r') as f:
        json_dict = json.load(f)
    query = Query._from_json(json_dict)
    assert query
    assert isinstance(query, OpenSearchQuery)
    assert isinstance(query.entity, Agent)
    assert query.entity.name == 'EGFR'
    assert query.entity_role == 'object'
    assert query.stmt_type == 'Inhibition'
    assert isinstance(query.path_stmt, Inhibition)
    assert query.path_stmt.subj is None
    assert query.terminal_ns == ['chebi']


def test_open_query_to_json():
    ag = Agent('EGFR', db_refs={'HGNC': '3236'})
    query = OpenSearchQuery(ag, 'Inhibition', 'object', ['chebi'])
    assert query
    json = query.to_json()
    assert json.get('type') == 'open_search_query'
    assert json.get('stmt_type') == 'Inhibition'
    assert json.get('entity_role') == 'object'
    assert json.get('terminal_ns') == ['chebi']
    deserialize_query = Query._from_json(json)
    json2 = deserialize_query.to_json()
    assert json == json2, {'json': json, 'json2': json2}


def test_stringify_open_query():
    ag = Agent('EGFR', db_refs={'HGNC': '3236'})
    query = OpenSearchQuery(ag, 'Inhibition', 'object', ['chebi'])
    query_str = str(query)
    assert query_str == (
        "OpenSearchQuery(stmt=Inhibition(None, EGFR()). Terminal namespace="
        "['chebi']")


def test_open_query_to_english():
    ag = Agent('EGFR', db_refs={'HGNC': '3236'})
    q1 = OpenSearchQuery(ag, 'Inhibition', 'object', ['chebi', 'chembl'])
    q2 = OpenSearchQuery(ag, 'Inhibition', 'subject', ['hgnc'])
    q3 = OpenSearchQuery(ag, 'Activation', 'subject')
    assert q1.to_english() == 'What inhibits EGFR? (CHEBI, CHEMBL)', q1.to_english()
    assert q2.to_english() == 'What does EGFR inhibit? (HGNC)'
    assert q3.to_english() == 'What does EGFR activate?'


def test_get_sign():
    ag = Agent('EGFR', db_refs={'HGNC': '3236'})
    # When entity role is object, sign is always 0 (sign of upstream node)
    query = OpenSearchQuery(ag, 'Inhibition', 'object', ['chebi'])
    for mc_type in ['pysb', 'pybel', 'signed_graph', 'unsigned_graph']:
        assert query.get_sign(mc_type) == 0
    # Entity role is subject
    # Always 0 for unsigned graph
    query = OpenSearchQuery(ag, 'Inhibition', 'subject', ['chebi'])
    assert query.get_sign('unsigned_graph') == 0
    # For others, depends on statement type
    for mc_type in ['pysb', 'pybel', 'signed_graph']:
        assert query.get_sign(mc_type) == 1
    query = OpenSearchQuery(ag, 'Activation', 'subject', ['chebi'])
    for mc_type in ['pysb', 'pybel', 'signed_graph']:
        assert query.get_sign(mc_type) == 0


def test_grounding_from_gilda():
    agent = get_agent_from_gilda('MAPK1')
    assert isinstance(agent, Agent)
    assert agent.name == 'MAPK1'
    assert agent.db_refs == {'TEXT': 'MAPK1', 'HGNC': '6871', 'UP': 'P28482',
                             'MESH': 'C535150', 'EGID': '5594'}, agent.db_refs

    # test with lower case
    agent = get_agent_from_gilda('mapk1')
    assert isinstance(agent, Agent)
    assert agent.name == 'MAPK1'
    assert agent.db_refs == {'TEXT': 'mapk1', 'HGNC': '6871', 'UP': 'P28482',
                             'MESH': 'C535150', 'EGID': '5594'}, agent.db_refs
    # other agent
    agent = get_agent_from_gilda('BRAF')
    assert isinstance(agent, Agent)
    assert agent.name == 'BRAF'
    assert agent.db_refs == {'TEXT': 'BRAF', 'EGID': '673', 'MESH': 'C482119',
                             'HGNC': '1097', 'UP': 'P15056'}, agent.db_refs


def test_agent_from_trips():
    ag = get_agent_from_trips('MAP2K1')
    assert isinstance(ag, Agent)
    assert ag.name == 'MAP2K1'
    assert not ag.mods
    ag_phos = get_agent_from_trips('the phosphorylated MAP2K1')
    assert ag_phos.mods


def test_generic_agent_from_text():
    agent = get_agent_from_gilda('MAPK1')
    assert isinstance(agent, Agent)
    assert agent.name == 'MAPK1'
    assert agent.db_refs == {'TEXT': 'MAPK1', 'HGNC': '6871', 'UP': 'P28482',
                             'MESH': 'C535150', 'EGID': '5594'}, agent.db_refs
    assert not agent.mods
    ag_phos = get_agent_from_trips('the phosphorylated MAP2K1')
    assert ag_phos.db_refs.get('HGNC') == '6840'
    assert ag_phos.mods
