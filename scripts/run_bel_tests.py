import os
import sys
import indra
import pickle
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
    usage = "Usage: %s dump|run" % sys.argv[0]
    if len(sys.argv) < 2 or sys.argv[1] not in ('dump', 'run'):
        print(usage)
        sys.exit(1)
    mode = sys.argv[1]

    indirect_stmts = get_indirect_stmts()
    tests = [StatementCheckingTest(stmt) for stmt in indirect_stmts]
    if mode == 'dump':
        with open('small_corpus_tests.pkl', 'wb') as f:
            pickle.dump(tests, f)
    elif mode == 'run':
        ctypes = ['rasmodel']
        models = [load_model(ctype, 'models/%s/config.yaml' % ctype)
                  for ctype in ctypes]
        tm = TestManager(models, tests)
        tm.make_tests(ScopeTestConnector())
        tm.run_tests()
        print(tm.test_results)

