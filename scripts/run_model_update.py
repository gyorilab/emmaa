from emmaa.model import EmmaaModel


if __name__ == '__main__':
    cancer_types = ('aml', 'brca', 'luad', 'paad', 'prad', 'skcm')

    for ctype in cancer_types:
        em = EmmaaModel.load_from_s3(ctype)
        em.get_new_readings()
        em.save_to_s3()
        em.upload_to_ndex()