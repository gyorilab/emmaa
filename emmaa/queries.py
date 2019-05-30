from inflection import camelize, underscore
from collections import OrderedDict as _o
from indra.statements.statements import Statement, Agent, get_all_descendants
from indra.databases.hgnc_client import get_hgnc_id
from indra.databases.chebi_client import get_chebi_id_from_name
from indra.databases.mesh_client import get_mesh_id_name
from indra.preassembler.grounding_mapper import gm


class Query(object):
    """The parent class of all query types."""
    @classmethod
    def _from_json(cls, json_dict):
        query_type = json_dict.get('type')
        query_cls = query_cls_from_type(query_type)
        query = query_cls._from_json(json_dict)
        return query


class StructuralProperty(Query):
    pass


class PathProperty(Query):
    """This type of query requires finding a mechanistic causally consistent
    path that satisfies query statement.

    Parameters:
    ----------
    path_stmt : indra.statements.Statement
        A path to look for in the model represented as INDRA statement.
    entity_constraints : dict(list(indra.statements.Agent))
        A dictionary containing lists of Agents to be included in or excluded
        from the path.
    relationship_constraints : dict(list(str))
        A dictionary containing lists of Statement types to include in or
        exclude from the path.
    """
    def __init__(self, path_stmt, entity_constraints=None,
                 relationship_constraints=None):
        self.path_stmt = path_stmt
        if entity_constraints:
            self.include_entities = entity_constraints.get('include')
            self.exclude_entities = entity_constraints.get('exclude')
        else:
            self.include_entities = None
            self.exclude_entities = None
        if relationship_constraints:
            self.include_rels = relationship_constraints.get('include')
            self.exclude_rels = relationship_constraints.get('exclude')
        else:
            self.include_rels = None
            self.exclude_rels = None

    def to_json(self):
        query_type = underscore(type(self).__name__)
        json_dict = _o(type=query_type)
        json_dict['path'] = self.path_stmt.to_json()
        json_dict['entity_constraints'] = {}
        if self.include_entities:
            json_dict['entity_constraints']['include'] = [
                ec.to_json() for ec in self.include_entities]
        if self.exclude_entities:
            json_dict['entity_constraints']['exclude'] = [
                ec.to_json() for ec in self.exclude_entities]
        json_dict['relationship_constraints'] = {}
        if self.include_rels:
            json_dict['relationship_constraints']['include'] = [
                {'type': rel} for rel in self.include_rels]
        if self.exclude_rels:
            json_dict['relationship_constraints']['exclude'] = [
                {'type': rel} for rel in self.exclude_rels]
        return json_dict

    @classmethod
    def _from_json(cls, json_dict):
        path_stmt_json = json_dict.get('path')
        path_stmt = Statement._from_json(path_stmt_json)
        for ag in path_stmt.agent_list():
            ag = add_db_refs(ag)
        ent_constr_json = json_dict.get('entity_constraints')
        entity_constraints = None
        if ent_constr_json:
            entity_constraints = {}
            for key, value in ent_constr_json.items():
                entity_constraints[key] = [
                    add_db_refs(Agent._from_json(ec)) for ec in value]
        rel_constr_json = json_dict.get('relationship_constraints')
        relationship_constraints = None
        if rel_constr_json:
            relationship_constraints = {}
            for key, value in rel_constr_json.items():
                relationship_constraints[key] = [
                    rel_type['type'] for rel_type in value]
        query = cls(path_stmt, entity_constraints, relationship_constraints)
        return query


class SimpleInterventionProperty(Query):
    pass


class ComparativeInterventionProperty(Query):
    pass


def query_cls_from_type(query_type):
    query_classes = get_all_descendants(Query)
    for query_class in query_classes:
        if query_class.__name__.lower() == camelize(query_type).lower():
            return query_class
    raise NotAQueryType(f'{query_type} is not recognized as a query type!')


def add_db_refs(agent):
    """Add db_refs to an Agent object and update a name if needed."""
    grounding = get_grounding_from_name(agent.name)
    if not grounding:
        grounding = get_grounding_from_name(agent.name.upper())
        ag.name = agent.name.upper()
    agent.db_refs = {grounding[0]: grounding[1]}
    return agent


def get_grounding_from_name(name):
    """Return grounding given an agent name."""
    # See if it's a gene name
    hgnc_id = get_hgnc_id(name)
    if hgnc_id:
        return ('HGNC', hgnc_id)

    # Check if it's in the grounding map
    try:
        refs = gm[name]
        if isinstance(refs, dict):
            for dbn, dbi in refs.items():
                if dbn != 'TEXT':
                    return (dbn, dbi)
    # If not, search by text
    except KeyError:
        pass

    chebi_id = get_chebi_id_from_name(name)
    if chebi_id:
        return ('CHEBI', f'CHEBI: {chebi_id}')

    mesh_id, _ = get_mesh_id_name(name)
    if mesh_id:
        return ('MESH', mesh_id)

    return None


class GroundingError(Exception):
    pass


class NotAQueryType(Exception):
    pass
