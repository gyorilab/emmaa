from emmaa.model import EmmaaModel


if __name__ == '__main__':
    cancer_types = ('paad', 'skcm', 'aml', 'luad', 'prad', 'food_insecurity',
                    'rasmachine', 'brca')

    for ctype in cancer_types:
        em = EmmaaModel.load_from_s3(ctype)
        em.get_new_readings()
        em.save_to_s3()
        em.update_to_ndex()
