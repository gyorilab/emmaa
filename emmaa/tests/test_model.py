import datetime
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