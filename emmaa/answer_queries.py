from indra.statements.statements import get_statement_by_name
from indra.explanation.model_checker import ModelChecker
from emmaa.model_tests import (StatementCheckingTest, ScopeTestConnector,
                               ModelManager)
from emmaa.model import EmmaaModel
from emmaa.util import get_s3_client


def get_statement_by_query(query_dict):
    """Get an INDRA Statement object given a query dictionary"""
    stmt_type = query_dict['query']['typeSelection']
    stmt_class = get_statement_by_name(stmt_type)
    subj = query_dict['query']['subjectSelection']
    obj = query_dict['query']['objectSelection']
    stmt = stmt_class(subj, obj)
    return stmt


def get_model_list(query_dict):
    return query_dict['query']['models']


def answer_immediate_query(query_dict):
    stmt = get_statement_by_name(query_dict)
    model_names = get_model_list(query_dict)
    results = {}
    for model_name in model_names:
        mm = load_model_manager_from_s3(model_name)
        response = mm.answer_query(stmt)
        results[model_name] = response
    return results


def load_model_manager_from_s3(model_name):
    client = get_s3_client()
    key = f'models/{model_name}/latest_model_manager.pkl'
    obj = client.get_object(Bucket='emmaa', Key=key)
    model_manager = pickle.loads(obj['Body'].read())
    return model_manager
