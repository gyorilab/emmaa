import logging
from inflection import underscore
from collections import OrderedDict as _o
import gilda
from indra.sources import trips
from indra.ontology.standardize import \
    standardize_agent_name
from indra.statements.statements import *
from indra.assemblers.english.assembler import _assemble_agent_str, \
    EnglishAssembler, statement_base_verb, statement_present_verb
from indra.assemblers.pybel.assembler import _get_agent_node
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
        agent = _assemble_agent_str(self.entity).agent_str
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


class OpenSearchQuery(Query):
    """This type of query requires doing an open ended breadth-first search
    to find paths satisfying the query.

    Parameters
    ----------
    entity : indra.statements.Agent
        An entity to simulate the model for.
    stmt_type : str
        Name of statement type.
    entity_role : str
        What role entity should play in statement (subject or object).
    terminal_ns : list[str]
        Force a path to terminate when any of the namespaces in this list
        are encountered and only yield paths that terminate at these
        namepsaces

    Attributes
    ----------
    path_stmt : indra.statements.Statement
        An INDRA statement having its subject or object set to None to
        represent open search query.
    """
    def __init__(self, entity, stmt_type, entity_role, terminal_ns=None):
        self.entity = entity
        self.stmt_type = stmt_type
        self.entity_role = entity_role
        self.terminal_ns = terminal_ns
        self.path_stmt = self.make_stmt()

    def make_stmt(self):
        stmt_type = self.stmt_type
        if self.entity_role == 'subject':
            if self.stmt_type == 'IncreaseAmount':
                stmt_type = 'Activation'
            elif self.stmt_type == 'DecreaseAmount':
                stmt_type = 'Inhibition'
        stmt_class = get_statement_by_name(stmt_type)
        if self.entity_role == 'subject':
            subj = self.entity
            obj = None
        elif self.entity_role == 'object':
            subj = None
            obj = self.entity
        stmt = stmt_class(subj, obj)
        return stmt

    def get_sign(self, mc_type):
        if mc_type == 'unsigned_graph' or self.entity_role == 'object':
            sign = 0
        elif isinstance(self.path_stmt, RegulateActivity):
            sign = 0 if self.path_stmt.is_activation else 1
        elif isinstance(self.path_stmt, RegulateAmount):
            sign = 1 if isinstance(self.path_stmt, DecreaseAmount) else 0
        else:
            raise ValueError('Could not determine sign')
        return sign

    def matches_key(self):
        key = self.entity.matches_key()
        key += self.stmt_type
        key += self.entity_role
        if self.terminal_ns:
            for ns in self.terminal_ns:
                key += ns
        return mk_str(key)

    def to_json(self):
        query_type = self.get_type()
        json_dict = _o(type=query_type)
        json_dict['entity'] = self.entity.to_json()
        json_dict['stmt_type'] = self.stmt_type
        json_dict['entity_role'] = self.entity_role
        json_dict['terminal_ns'] = self.terminal_ns
        return json_dict

    @classmethod
    def _from_json(cls, json_dict):
        ent_json = json_dict.get('entity')
        entity = Agent._from_json(ent_json)
        stmt_type = json_dict.get('stmt_type')
        entity_role = json_dict.get('entity_role')
        terminal_ns = json_dict.get('terminal_ns')
        query = cls(entity, stmt_type, entity_role, terminal_ns)
        return query

    def __str__(self):
        parts = [f'OpenSearchQuery(stmt={self.path_stmt}.']
        if self.terminal_ns:
            parts.append(f' Terminal namespace={self.terminal_ns}')
        return ''.join(parts)

    def __repr__(self):
        return str(self)

    def to_english(self):
        agent = _assemble_agent_str(self.entity).agent_str
        if self.entity_role == 'subject':
            verb = statement_base_verb(self.stmt_type.lower())
            verb = verb[0].lower() + verb[1:]
            sentence = f'What does {agent} {verb}?'
        elif self.entity_role == 'object':
            verb = statement_present_verb(self.stmt_type.lower())
            verb = verb[0].lower() + verb[1:]
            sentence = f'What {verb} {agent}?'
        sentence = sentence[0].upper() + sentence[1:]
        if self.terminal_ns:
            sentence += f' ({", ".join(self.terminal_ns).upper()})'
        return sentence

    def get_entities(self):
        return [self.entity]


# This is the general method to get a grounding agent from text but it doesn't
# handle agent state which is required for dynamic queries
def get_agent_from_gilda(ag_name):
    """Return an INDRA Agent object by grounding its entity text with Gilda."""
    matches = gilda.ground(ag_name)
    if not matches:
        raise GroundingError(
            f"Could not find grounding for {ag_name} with Gilda.")
    agent = Agent(ag_name,
                  db_refs={'TEXT': ag_name,
                           matches[0].term.db: matches[0].term.id})
    standardize_agent_name(agent, standardize_refs=True)
    return agent


# This is the method that dynamical queries use to represent agents with
# state
def get_agent_from_trips(ag_text, service_host='http://34.230.33.149:8002/cgi/'):
    """Return an INDRA Agent object by grounding its entity text with TRIPS."""
    tp = trips.process_text(ag_text, service_host=service_host)
    agent_list = tp.get_agents()
    if not agent_list:
        raise GroundingError(
            f"Could not find grounding for {ag_text} with TRIPS.")
    return agent_list[0]


def get_agent_from_text(ag_text):
    """
    Return an INDRA Agent object by grounding its entity text with either
    Gilda or TRIPS.
    """
    try:
        agent = get_agent_from_gilda(ag_text)
        logger.info('Got agent from Gilda')
    except GroundingError:
        try:
            agent = get_agent_from_trips(ag_text)
            logger.info('Got agent from TRIPS')
        except GroundingError:
            raise GroundingError(f'Could not find grounding for {ag_text}.')
    return agent


class GroundingError(Exception):
    pass
