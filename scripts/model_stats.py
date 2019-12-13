import numpy
import pickle
from emmaa.model import get_model_stats
import matplotlib.pyplot as plt

models = {'disease': ['aml', 'brca', 'skcm', 'prad', 'paad', 'luad'],
          'pathway': ['rasmachine'],
          'manual': ['rasmodel', 'marm_model'],
          'wm': ['food_insecurity']}


if __name__ == '__main__':
    all_models = []
    for k, v in models.items():
        all_models += v

    #stats = {}
    #for model in all_models:
    #    stats[model] = get_model_stats(model, 'json')

    TLIMIT = 90

    with open('stats.pkl', 'rb') as fh:
        stats = pickle.load(fh)

    deltas = []
    deltas_applied = []
    deltas_passed = []
    for model in models['disease'] + models['pathway']:
        numstmt = \
            stats[model]['changes_over_time']['number_of_statements'][-TLIMIT:]
        deltas += list(numpy.diff(numstmt))
        numapp = \
            stats[model]['changes_over_time']['number_applied_tests'][-TLIMIT:]
        deltas_applied += list(numpy.diff(numapp))
        for mt in ['pysb', 'pybel', 'signed_graph', 'unsigned_graph']:
            num_passed = \
                stats[model]['changes_over_time'][mt]['passed_ratio'][-TLIMIT:]
            deltas_passed += list(numpy.diff(num_passed))
    plt.ion()
    plt.figure()
    plt.hist(deltas, 100)
    plt.xlabel('Number of statements added each day')
    plt.figure()
    plt.hist(deltas_applied, 100)
    plt.xlabel('Number of new tests applied each day')
    plt.yscale('log')
    plt.figure()
    plt.hist(deltas_passed, 100)
    plt.xlabel('Fraction of new tests passed each day')
    plt.yscale('log')
