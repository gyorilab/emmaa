import json
import pickle
import datetime
from emmaa.model import EmmaaModel
from emmaa.statements import EmmaaStatement


def update_cancer(cancer_type):
    """Update the model for the given cancer.

    A JSON config file must be present for the given cancer type, located in
    the models/<cancer_type>/config.json.

    Parameters
    ----------
    cancer_type : str
        A short string which is the name of the cancer, and corresponds to a
        directory in the models directory, as described above.
    """
    print(cancer_type)
    with open(f'models/{cancer_type}/prior_stmts.pkl', 'rb') as fh:
        stmts = pickle.load(fh)
    config = json.load(open(f'models/{cancer_type}/config.json', 'r'))
    em = EmmaaModel(cancer_type, config)
    ess = [EmmaaStatement(st, datetime.datetime.now(), []) for st in stmts]
    em.add_statements(ess)
    em.save_to_s3()
    return


def main():
    cancer_types = ('aml', 'brca', 'luad', 'paad', 'prad', 'skcm')

    for ctype in cancer_types:
        update_cancer(ctype)


if __name__ == '__main__':
    main()
