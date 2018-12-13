import os
import indra
from indra.sources import bel
from indra.assemblers.english import EnglishAssembler
from emmaa.model import load_model
from emmaa.model_tests import TestManager, ScopeTestConnector, \
    StatementCheckingTest


def get_indirect_stmts():
    lcpath = os.path.join(indra.__path__[0], os.pardir, 'data',
                          'small_corpus.bel')
    bp = bel.process_belscript(lcpath)
    indirect_stmts = [st for st in bp.statements
                      if not st.evidence[0].epistemics.get('direct')]
    return indirect_stmts


if __name__ == '__main__':
    indirect_stmts = get_indirect_stmts()
    tests = [StatementCheckingTest(stmt) for stmt in indirect_stmts]
    ctypes = ['luad']
    models = [load_model(ctype, f'models/{ctype}/config.yaml')
              for ctype in ctypes]
    tm = TestManager(models, tests)
    tm.make_tests(ScopeTestConnector())
    tm.run_tests()
    print(tm.test_results)

