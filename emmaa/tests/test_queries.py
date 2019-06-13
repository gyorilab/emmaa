import json
from indra.statements import Phosphorylation, Agent
from emmaa.queries import Query, PathProperty


# Tell nose to not run tests in the imported modules
Phosphorylation.__test__ = False
Agent.__test__ = False
Query.__test__ = False
PathProperty.__test__ = False


def test_path_property_from_json():
    with open('path_property_query.json', 'r') as f:
        json_dict = json.load(f)
    query = Query._from_json(json_dict)
    assert query
    assert isinstance(query, PathProperty)
    assert isinstance(query.path_stmt, Phosphorylation), query.path_stmt
    assert query.path_stmt.enz.name == 'EGFR', query.path_stmt
    assert query.path_stmt.sub.name == 'ERK', query.path_stmt
    assert isinstance(query.exclude_entities[0], Agent)
    assert query.exclude_entities[0].name == 'PI3K'
    assert not query.include_entities, query.include_entities
    assert set(query.exclude_rels) == set(['IncreaseAmount', 'DecreaseAmount'])
    assert not query.include_rels, query.include_rels


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
