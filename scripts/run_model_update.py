import yaml
import pickle
import datetime
from emmaa.model import EmmaaModel
from emmaa.statements import EmmaaStatement


if __name__ == '__main__':
    cancer_types = ('aml', 'brca', 'luad', 'paad', 'prad', 'skcm')

    for ctype in cancer_types:
        config = yaml.load(open('models/%s/config.yaml' % ctype, 'r'))
        em = EmmaaModel(ctype, config)
        em.load_from_s3()
        em.get_new_readings()
        em.save_to_s3()
