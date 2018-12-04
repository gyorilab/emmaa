import yaml
import pickle
import datetime
from emmaa.model import EmmaaModel
from emmaa.statements import EmmaaStatement


if __name__ == '__main__':
    cancer_types = ('aml', 'brca', 'luad', 'paad', 'prad', 'skcm')

    for ctype in cancer_types:
        print(ctype)
        with open(f'models/{ctype}/prior_stmts.pkl', 'rb') as fh:
            stmts = pickle.load(fh)
        config = yaml.load(open(f'models/{ctype}/config.yaml', 'r'))
        em = EmmaaModel(ctype, config)
        ess = [EmmaaStatement(st, datetime.datetime.now(), []) for st in stmts]
        em.add_statements(ess)
        em.save_to_s3()