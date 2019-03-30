from emmaa.model import EmmaaModel


if __name__ == '__main__':
    cancer_types = ('aml', 'brca', 'luad', 'paad', 'prad', 'skcm',
                    'rasmachine')

    for ctype in cancer_types:
        em = EmmaaModel.load_from_s3(ctype)
        em.get_new_readings()
        em.save_to_s3()
        em.update_to_ndex()
