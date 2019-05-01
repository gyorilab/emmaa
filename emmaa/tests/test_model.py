import datetime
from indra.statements import Activation, ActivityCondition, Phosphorylation, \
    Agent, Evidence
from emmaa.model import EmmaaModel
from emmaa.priors import SearchTerm
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
    """Test the json structure and content of EmmaaModel.to_json() output"""
    indra_stmts = \
        [Activation(Agent('BRAF', db_refs={'HGNC': '20974'}),
                    Agent('MAP2K1'),
                    evidence=[Evidence(text='BRAF activates MAP2K1.')]),
         Activation(Agent('MAP2K1',
                          activity=ActivityCondition('activity', True)),
                    Agent('MAPK1'),
                    evidence=[Evidence(text='Active MAP2K1 activates MAPK1.')])
         ]
    st = SearchTerm('gene', 'MAP2K1', db_refs={}, search_term='MAP2K1')
    emmaa_stmts = [EmmaaStatement(stmt, datetime.datetime.now(), [st])
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

    # Need hashes to be strings so that javascript can read them
    assert isinstance(emmaa_model_json['stmts'][0]['stmt']['evidence'][0][
                          'source_hash'], str)


def test_filter_relevance():
    config_dict = {'ndex': {'network': 'a08479d1-24ce-11e9-bb6a-0ac135e8bacf'},
                   'search_terms': [{'db_refs': {'HGNC': '20974'},
                                     'name': 'MAPK1',
                                     'search_term': 'MAPK1',
                                     'type': 'gene'}]}
    indra_stmts = \
        [Activation(Agent('BRAF', db_refs={'HGNC': '20974'}),
                    Agent('MAP2K1'),
                    evidence=[Evidence(text='BRAF activates MAP2K1.',
                                       source_api='assertion')]),
         Activation(Agent('MAP2K1',
                          activity=ActivityCondition('activity', True)),
                    Agent('MAPK1'),
                    evidence=[Evidence(text='Active MAP2K1 activates '
                                            'MAPK1.',
                                       source_api='assertion')])
         ]
    st = SearchTerm('gene', 'MAP2K1', db_refs={}, search_term='MAP2K1')
    emmaa_stmts = [EmmaaStatement(stmt, datetime.datetime.now(), [st])
                   for stmt in indra_stmts]

    # Try no filter first
    emmaa_model = EmmaaModel('test', config_dict)
    emmaa_model.extend_unique(emmaa_stmts)
    emmaa_model.run_assembly()
    assert len(emmaa_model.assembled_stmts) == 2, emmaa_model.assembled_stmts

    # Next do a prior_one filter
    config_dict['assembly'] = {'filter_relevance': 'prior_one'}
    emmaa_model = EmmaaModel('test', config_dict)
    emmaa_model.extend_unique(emmaa_stmts)
    emmaa_model.run_assembly()
    assert len(emmaa_model.assembled_stmts) == 1, emmaa_model.assembled_stmts
    assert emmaa_model.assembled_stmts[0].obj.name == 'MAPK1'

    # Next do a prior_all filter
    config_dict['assembly'] = {'filter_relevance': 'prior_all'}
    emmaa_model = EmmaaModel('test', config_dict)
    emmaa_model.extend_unique(emmaa_stmts)
    emmaa_model.run_assembly()
    assert len(emmaa_model.assembled_stmts) == 0
