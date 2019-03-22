import os
import indra
import pickle
import argparse
from indra.sources import bel
from indra.tools import assemble_corpus as ac
from emmaa.model import EmmaaModel
from emmaa.model_tests import TestManager, ScopeTestConnector, \
    StatementCheckingTest


def get_indirect_stmts(corpus):
    cpath = os.path.join(indra.__path__[0], os.pardir, 'data',
                         f'{corpus}_corpus.bel')
    bp = bel.process_belscript(cpath)
    indirect_stmts = [st for st in bp.statements
                      if not st.evidence[0].epistemics.get('direct')]
    stmts = ac.run_preassembly(indirect_stmts, return_toplevel=False)
    return stmts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--corpus', default='large')
    parser.add_argument('--mode', default='dump')
    args = parser.parse_args()

    indirect_stmts = get_indirect_stmts(args.corpus)
    tests = [StatementCheckingTest(stmt) for stmt in indirect_stmts]
    if args.mode == 'dump':
        with open(f'{args.corpus}_corpus_tests.pkl', 'wb') as f:
            pickle.dump(tests, f)
    elif args.mode == 'run':
        ctypes = ['rasmodel']
        models = [EmmaaModel(ctype) for ctype in ctypes]
        tm = TestManager(models, tests)
        tm.make_tests(ScopeTestConnector())
        tm.run_tests()
        print(tm.test_results)

