from os.path import abspath, dirname, join
from indra.tools import assemble_corpus as ac
from indra.databases import hgnc_client
from indra.assemblers.indranet import IndraNetAssembler
from util import nx_to_graph_commons

stmts_path = join(dirname(abspath(__file__)), '..', '..', '..',
                         'covid-19', 'stmts')
gordon_stmts_path = join(stmts_path, 'gordon_ndex_stmts.pkl')
combined_stmts_path = join(stmts_path, 'cord19_combined_stmts.pkl')

gordon_stmts = ac.load_statements(gordon_stmts_path)
comb_stmts = ac.load_statements(combined_stmts_path)

# Get human interactors of viral proteins from Gordon et al.
hgnc_ids = [ag.db_refs['HGNC'] for stmt in gordon_stmts
            for ag in stmt.agent_list()
            if ag is not None and 'HGNC' in ag.db_refs]
hgnc_names = [hgnc_client.get_hgnc_name(id) for id in hgnc_ids]

# Filter statements to only those involving at least one of the given
# genes
filt_stmts = ac.filter_gene_list(comb_stmts, hgnc_names, policy='all',
                                 allow_families=True)
filt_stmts = [s for s in filt_stmts if s.agent_list()[0] is not None]

# Add back the Gordon et al. statements
all_stmts = filt_stmts + gordon_stmts

ina = IndraNetAssembler(all_stmts)
dg = ina.make_model(graph_type='digraph')
nx_to_graph_commons(dg, 'Gordon', 'gordon_gc.json',
                    graph_description="SARS-Cov-2 PPIs")
# Save combined statements
ac.dump_statements(all_stmts, 'gordon_stmts.pkl')

