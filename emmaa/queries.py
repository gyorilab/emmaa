from inflection import camelize, underscore
from collections import OrderedDict as _o
from indra.statements.statements import Statement, Agent, get_all_descendants


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
        self.include_entities = entity_constraints.get('include')
        self.exclude_entities = entity_constraints.get('exclude')
        self.include_rels = relationship_constraints.get('include')
        self.exclude_rels = relationship_constraints.get('exclude')

    def to_json(self):
        query_type = underscore(type(self).__name__)
        json_dict = _o(type=query_type)
        json_dict['path'] = self.path_stmt.to_json()
        json_dict['entity_constraints'] = {}
        json_dict['entity_constraints']['include'] = [ec.to_json() for ec in
                                                      self.include_entities]
        json_dict['entity_constraints']['exclude'] = [ec.to_json() for ec in
                                                      self.exclude_entities]
        json_dict['relationship_constraints'] = {}
        json_dict['relationship_constraints']['include'] = [
            {'type': rel} for rel in self.include_rels]
        json_dict['relationship_constraints']['exclude'] = [
            {'type': rel} for rel in self.exclude_rels]
        return json_dict

    @classmethod
    def _from_json(cls, json_dict):
        path_stmt_json = json_dict.get('path')
        path_stmt = Statement._from_json(path_stmt_json)
        ent_constr_json = json_dict.get('entity_constraints')
        entity_constraints = {}
        for key, value in ent_constr_json.items():
            entity_constraints[key] = [Agent._from_json(ec) for ec in value]
        rel_constr_json = json_dict.get('relationship_constraints')
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


class NotAQueryType(Exception):
    pass
