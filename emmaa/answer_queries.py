import logging
import pickle
from datetime import datetime
from indra.statements.statements import get_statement_by_name
from indra.statements.agent import Agent
from indra.databases.hgnc_client import get_hgnc_id
from indra.databases.chebi_client import get_chebi_id_from_name
from indra.databases.mesh_client import get_mesh_id_name
from indra.preassembler.grounding_mapper import gm
from emmaa.util import get_s3_client, make_date_str
from emmaa.db import get_db


logger = logging.getLogger(__name__)


model_manager_cache = {}


def answer_immediate_query(user_email, query_dict, model_names, subscribe,
                           db_name='primary'):
    """Save an immediate query in a database and answer it for each model."""
    db = get_db(db_name)
    db.put_queries(user_email, query_dict, model_names, subscribe)
    # Check if the query has already been answered for any of given models and
    # retrieve the results from database.
    saved_results = db.get_results_from_query(query_dict, model_names)
    checked_models = {res[0] for res in saved_results}
    if checked_models == set(model_names):
        return format_results(saved_results)
    # Run answer queries mechanism for models for which result was not found.
    stmt = get_statement_by_query(query_dict)
    new_results = []
    new_date = datetime.now()
    for model_name in model_names:
        if model_name not in checked_models:
            mm = load_model_manager_from_s3(model_name)
            response = mm.answer_query(stmt)
            new_results.append((model_name, query_dict, response, new_date))
            if subscribe:
                db.put_results(model_name, [(query_dict, response)])
    all_results = saved_results + new_results
    return format_results(all_results)


def answer_registered_queries(model_name, model_manager=None, db_name='primary'):
    """Retrieve queries registered on database for a given model, answer them,
    and put results to a database.
    """
    if not model_manager:
        model_manager = load_model_manager_from_s3(model_name)
    db = get_db(db_name)
    query_dicts = db.get_queries(model_name)
    query_stmt_pairs = get_query_stmt_pairs(query_dicts)
    results = model_manager.answer_queries(query_stmt_pairs)
    db.put_results(model_name, results)


def get_registered_queries(user_email, db_name='primary'):
    """Get formatted results to queries registered by user."""
    db = get_db(db_name)
    results = db.get_results(user_email)
    return format_results(results)


def format_results(results):
    """Format db output to a standard json structure."""
    formatted_results = []
    for result in results:
        formatted_result = {}
        formatted_result['model'] = result[0]
        formatted_result['query'] = result[1]
        response_json = result[2]
        response_hashes = [key for key in response_json.keys()]
        sentence_link_pairs = response_json[response_hashes[0]]
        response_list = []
        for ix, (sentence, link) in enumerate(sentence_link_pairs):
            if ix > 0:
                response_list.append('<br>')
            response_list.append(
                f'<a href="{link}" target="_blank" '
                f'class="status-link">{sentence}</a>')
        response = ''.join(response_list)
        formatted_result['response'] = response
        formatted_result['date'] = make_date_str(result[3])
        formatted_results.append(formatted_result)
    return formatted_results


def get_query_stmt_pairs(queries):
    """Return a list of tuples each containing a query dictionary and a
    statement derived from it.
    """
    query_stmt_pairs = []
    for query_dict in queries:
        query_stmt_pairs.append(
            (query_dict, get_statement_by_query(query_dict)))
    return query_stmt_pairs


def get_statement_by_query(query_dict):
    """Get an INDRA Statement object given a query dictionary."""
    stmt_type = query_dict['typeSelection']
    stmt_class = get_statement_by_name(stmt_type)
    subj = get_agent_from_name(query_dict['subjectSelection'])
    obj = get_agent_from_name(query_dict['objectSelection'])
    stmt = stmt_class(subj, obj)
    return stmt


def load_model_manager_from_s3(model_name):
    model_manager = model_manager_cache.get(model_name)
    if model_manager:
        logger.info(f'Loaded model manager for {model_name} from cache.')
        return model_manager
    client = get_s3_client()
    key = f'results/{model_name}/latest_model_manager.pkl'
    logger.info(f'Loading latest model manager for {model_name} model from '
                f'S3.')
    obj = client.get_object(Bucket='emmaa', Key=key)
    model_manager = pickle.loads(obj['Body'].read())
    model_manager_cache[model_name] = model_manager
    return model_manager


def get_agent_from_name(ag_name):
    """Return an INDRA Agent object."""
    ag = Agent(ag_name)
    grounding = get_grounding_from_name(ag_name)
    if not grounding:
        grounding = get_grounding_from_name(ag_name.upper())
        ag = Agent(ag_name.upper())
    if not grounding:
        raise GroundingError(f"Could not find grounding for {ag_name}.")
    ag.db_refs = {grounding[0]: grounding[1]}
    return ag


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
