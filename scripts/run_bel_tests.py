import yaml
from indra.sources import bel
from indra.assemblers.pysb import PysbAssembler
from indra.assemblers.english import EnglishAssembler
from emmaa.model import EmmaaModel
from emmaa.model_tests import TestManager, ScopeTestConnector, \
    StatementCheckingTest


def get_indirect_stmts():
    bp = bel.proces_belscript()
    indirect_stmts = [st for st in bp.statements
                      if not bp.evidence[0].epistemics('direct')]
    return indirect_stmts


def load_model(ctype):
    config = yaml.load(open(f'models/{ctype}/config.yaml', 'r'))
    em = EmmaaModel(ctype, config)
    em.load_from_s3()
    return em


if __name__ == '__main__'
    indirect_stmts = get_indirect_stmts()
    tests = [StatementCheckingTest(stmt) for stmt in indirect_stmts]
    ctypes = ['aml', 'brca', 'luad', 'paad', 'prad', 'skcm']
    models = []
    for ctype in ctypes:
        # load model from S3
        model = load_model(ctype)
        stmts = model.get_indra_stmts()
        pa = PysbAssembler()
        pa.add_statements(stmts)
        pysb_model = pa.make_model()
        models.append(pysb_model)
    # make TestManager
    tm = TestManager(models, tests)
    tm.make_tests(ScopeTestConnector())
    tm.run_tests()
    print(tm.test_results)

