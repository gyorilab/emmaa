import requests
from inflection import camelize, underscore
from collections import OrderedDict as _o
from indra.statements.statements import Statement, Agent, get_all_descendants,\
    mk_str, make_hash
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

    def matches(self, other):
        return self.matches_key() == other.matches_key()

    def matches_key(self):
        pass

    def get_hash(self):
        return make_hash(self.matches_key(), 14)

    def get_hash_with_model(self, model_name):
        key = (self.matches_key(), model_name)
        return make_hash(mk_str(key), 14)


class StructuralProperty(Query):
    pass


class PathProperty(Query):
    """This type of query requires finding a mechanistic causally consistent
    path that satisfies query statement.

    Parameters
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
            self.include_entities = entity_constraints.get('include', [])
            self.exclude_entities = entity_constraints.get('exclude', [])
        else:
            self.include_entities = []
            self.exclude_entities = []
        if relationship_constraints:
            self.include_rels = relationship_constraints.get('include', [])
            self.exclude_rels = relationship_constraints.get('exclude', [])
        else:
            self.include_rels = []
            self.exclude_rels = []
        self.entities = self.get_entities()

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
        ent_constr_json = json_dict.get('entity_constraints')
        entity_constraints = None
        if ent_constr_json:
            entity_constraints = {}
            for key, value in ent_constr_json.items():
                entity_constraints[key] = [Agent._from_json(ec) for ec
                                           in value]
        rel_constr_json = json_dict.get('relationship_constraints')
        relationship_constraints = None
        if rel_constr_json:
            relationship_constraints = {}
            for key, value in rel_constr_json.items():
                relationship_constraints[key] = [
                    rel_type['type'] for rel_type in value]
        query = cls(path_stmt, entity_constraints, relationship_constraints)
        return query

    def get_entities(self):
        """Return entities from the path statement and the inclusion list."""
        path_entities = self.path_stmt.agent_list()
        return path_entities + self.include_entities

    def matches_key(self):
        key = self.path_stmt.matches_key()
        if self.include_entities:
            for ent in sorted(self.include_entities,
                              key=lambda x: x.matches_key()):
                key += ent.matches_key()
        if self.exclude_entities:
            for ent in sorted(self.exclude_entities,
                              key=lambda x: x.matches_key()):
                key += ent.matches_key()
        if self.include_rels:
            for rel in sorted(self.include_rels):
                key += rel
        if self.exclude_rels:
            for rel in sorted(self.exclude_rels):
                key += rel
        return mk_str(key)

    def __str__(self):
        parts = [f'PathPropertyQuery(stmt={str(self.path_stmt)}.']
        if self.include_entities:
            inents = ', '.join([str(e) for e in self.include_entities])
            parts.append(f' Include entities: {inents}.')
        if self.exclude_entities:
            exents = ', '.join([str(e) for e in self.exclude_entities])
            parts.append(f' Exclude entities: {exents}.')
        if self.include_rels:
            inrels = ', '.join(self.include_rels)
            parts.append(f' Include relations: {inrels}.')
        if self.exclude_rels:
            exrels = ', '.join(self.exclude_rels)
            parts.append(f' Exclude relations: {exrels}.')
        return ''.join(parts)

    def __repr__(self):
        return str(self)


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


def get_agent_from_text(ag_name, use_grouding_service=True):
    """Return an INDRA Agent object."""
    grounding_url = "http://grounding.indra.bio/ground"
    if use_grouding_service:
        return get_agent_from_grounding_service(ag_name, grounding_url)
    return get_agent_from_local_grounding(ag_name)


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
        return ('CHEBI', f'CHEBI:{chebi_id}')

    mesh_id, _ = get_mesh_id_name(name)
    if mesh_id:
        return ('MESH', mesh_id)

    return None


def get_agent_from_local_grounding(ag_name):
    grounding = get_grounding_from_name(ag_name)
    if not grounding:
        grounding = get_grounding_from_name(ag_name.upper())
        ag_name = ag_name.upper()
    if not grounding:
        raise GroundingError(f"Could not find grounding for {ag_name}.")
    agent = Agent(ag_name, db_refs={grounding[0]: grounding[1]})
    return agent


def get_agent_from_grounding_service(ag_name, url):
    res = requests.post(url, json={'text': ag_name})
    rj = res.json()
    if not rj:
        raise GroundingError(f"Could not find grounding for {ag_name}.")
    agent = Agent(name=rj[0]['term']['entry_name'],
                  db_refs={rj[0]['term']['db']: rj[0]['term']['id']})
    return agent


class GroundingError(Exception):
    pass


class NotAQueryType(Exception):
    pass
