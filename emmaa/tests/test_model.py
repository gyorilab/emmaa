import datetime
from indra.sources import trips
from indra.statements import Phosphorylation, Agent, Evidence
from emmaa.model import EmmaaModel
from emmaa.statements import EmmaaStatement


def test_model_extend():
    ev1 = Evidence(pmid='1234', text='abcd', source_api='x')
    ev2 = Evidence(pmid='1234', text='abcde', source_api='x')
    ev3 = Evidence(pmid='1234', text='abcd', source_api='x')
    indra_sts = [Phosphorylation(None, Agent('a'), evidence=ev) for ev in
                 [ev1, ev2, ev3]]
    emmaa_sts = [EmmaaStatement(st, datetime.datetime.now(), ['x']) for st in
                 indra_sts]
    em = EmmaaModel('x', {'search_terms': [], 'ndex': {'network': None}})
    em.add_statements([emmaa_sts[0]])
    em.extend_unique(emmaa_sts[1:])
    assert len(em.stmts) == 2
    stmt = EmmaaStatement(Phosphorylation(None, Agent('b'), evidence=ev1),
                          datetime.datetime.now(), ['x'])
    em.extend_unique([stmt])
    assert len(em.stmts) == 3


def test_model_json():
    tp = trips.process_text('BRAF activates MAP2K1. '
                            'Active MAP2K1 activates MAPK1.')
    indra_stmts = tp.statements
    emmaa_stmts = [EmmaaStatement(stmt, datetime.datetime.now(), 'MAPK1')
                    for stmt in indra_stmts]
    config_dict = {'ndex': {'network': 'a08479d1-24ce-11e9-bb6a-0ac135e8bacf'},
                   'search_terms': [{'db_refs': {'HGNC': '20974'},
                                     'name': 'MAPK1',
                                     'search_term': 'MAPK1',
                                     'type': 'gene'}]}
    emmaa_model = EmmaaModel('test', config_dict)
    emmaa_model.add_statements(emmaa_stmts)

    emmaa_model_json = emmaa_model.to_json()

    # Test json structure
    assert emmaa_model_json['name'] == 'test'
    assert isinstance(emmaa_model_json['stmts'], list)
    assert emmaa_model_json['ndex_network'] == \
        'a08479d1-24ce-11e9-bb6a-0ac135e8bacf'

    # Test config
    assert emmaa_model_json['search_terms'][0]['type'] == 'gene'
    assert emmaa_model_json['search_terms'][0]['db_refs'] == {'HGNC': '20974'}

    # Test json statements
    assert 'BRAF activates MAP2K1.' == \
           emmaa_model_json['stmts'][0]['stmt']['evidence'][0]['text']
    assert 'BRAF activates MAP2K1.' == \
           emmaa_model_json['stmts'][0]['stmt']['evidence'][0]['text']
    assert 'Active MAP2K1 activates MAPK1.' == \
           emmaa_model_json['stmts'][1]['stmt']['evidence'][0]['text']
    assert emmaa_model_json['stmts'][0]['stmt']['subj']['name'] == 'BRAF'
    assert emmaa_model_json['stmts'][1]['stmt']['subj']['name'] == 'MAP2K1'
    assert emmaa_model_json['stmts'][1]['stmt']['obj']['name'] == 'MAPK1'

    assert emmaa_model_json['stmts'][0]['stmt']['evidence'][0]['source_api'] \
        == 'trips'
    # Need hashes to be strings so that javascript can read them
    assert isinstance(emmaa_model_json['stmts'][0]['stmt']['evidence'][0][
                          'source_hash'], str)
