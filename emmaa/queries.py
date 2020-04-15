import logging
from inflection import underscore
from collections import OrderedDict as _o
import gilda
from indra.sources import trips
from indra.preassembler.grounding_mapper.standardize import \
    standardize_agent_name
from indra.statements.statements import Statement, Agent, get_all_descendants,\
    mk_str, make_hash
from indra.assemblers.english.assembler import _assemble_agent_str, \
    EnglishAssembler
from bioagents.tra.tra import MolecularQuantity, TemporalPattern
from .util import get_class_from_name


logger = logging.getLogger(__name__)


class Query(object):
    """The parent class of all query types."""
    @classmethod
    def _from_json(cls, json_dict):
        query_type = json_dict.get('type')
        query_cls = get_class_from_name(query_type, Query)
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

    def get_type(self):
        return underscore(type(self).__name__)


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
        query_type = self.get_type()
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

    def to_english(self):
        ea = EnglishAssembler([self.path_stmt])
        return ea.make_model()


class SimpleInterventionProperty(Query):
    pass


class ComparativeInterventionProperty(Query):
    pass


class DynamicProperty(Query):
    """This type of query requires dynamic simulation of the model to check
    whether the queried temporal pattern is satisfied.

    Parameters
    ----------
    entity : indra.statements.Agent
        An entity to simulate the model for.
    pattern_type : str
        Type of temporal pattern. Accepted values: 'always_value', 'no_change',
        'eventual_value', 'sometime_value', 'sustained', 'transient'.
    quant_value : str or float
        Value of molecular quantity of entity of interest. Can be 'high' or
        'low' or a specific number.
    quant_type : str
        Type of molecular quantity of entity of interest. Default: qualitative.
    """
    def __init__(self, entity, pattern_type, quant_value=None,
                 quant_type='qualitative'):
        self.entity = entity
        self.pattern_type = pattern_type
        self.quant_value = quant_value
        self.quant_type = quant_type

    def get_temporal_pattern(self):
        """Return TemporalPattern object created with query properties."""
        mq = None
        if self.quant_value:
            mq = MolecularQuantity(self.quant_type, self.quant_value)
        tp = TemporalPattern(self.pattern_type, [self.entity], None, value=mq)
        return tp

    def matches_key(self):
        ent_matches_key = self.entity.matches_key()
        key = (ent_matches_key, self.pattern_type, self.quant_type,
               str(self.quant_value))
        return str(key)

    def to_json(self):
        query_type = self.get_type()
        json_dict = _o(type=query_type)
        json_dict['entity'] = self.entity.to_json()
        json_dict['pattern_type'] = self.pattern_type
        json_dict['quantity'] = {}
        json_dict['quantity']['type'] = self.quant_type
        json_dict['quantity']['value'] = self.quant_value
        return json_dict

    @classmethod
    def _from_json(cls, json_dict):
        ent_json = json_dict.get('entity')
        entity = Agent._from_json(ent_json)
        pattern_type = json_dict.get('pattern_type')
        quant_json = json_dict.get('quantity')
        quant_type = quant_json.get('type')
        quant_value = quant_json.get('value')
        query = cls(entity, pattern_type, quant_value, quant_type)
        return query

    def __str__(self):
        descr = (f'DynamicPropertyQuery(entity={self.entity}, '
                 f'pattern={self.pattern_type}, '
                 f'molecular quantity={(self.quant_type, self.quant_value)})')
        return descr

    def __repr__(self):
        return str(self)

    def to_english(self):
        agent = _assemble_agent_str(self.entity)
        agent = agent[0].upper() + agent[1:]
        if self.pattern_type == 'always_value':
            pattern = 'always'
        elif self.pattern_type == 'eventual_value':
            pattern = 'eventually'
        elif self.pattern_type == 'sometime_value':
            pattern = 'sometimes'
        elif self.pattern_type == 'no_change':
            pattern = 'not changing'
        else:
            pattern = self.pattern_type
        if self.quant_value:
            return f'{agent} is {pattern} {self.quant_value}.'
        return f'{agent} is {pattern}.'


# This is the general method to get a grounding agent from text but it doesn't
# handle agent state which is required for dynamic queries
def get_agent_from_text(ag_name):
    """Return an INDRA Agent object by grounding its entity text with Gilda."""
    matches = gilda.ground(ag_name)
    if not matches:
        raise GroundingError(f"Could not find grounding for {ag_name}.")
    agent = Agent(ag_name,
                  db_refs={'TEXT': ag_name,
                           matches[0].term.db: matches[0].term.id})
    standardize_agent_name(agent, standardize_refs=True)
    return agent


# This is the method that dynamical queries use to represent agents with
# state
def get_agent_from_trips(ag_text):
    tp = trips.process_text(ag_text)
    agent_list = tp.get_agents()
    if agent_list:
        return agent_list[0]
    return None

class GroundingError(Exception):
    pass
