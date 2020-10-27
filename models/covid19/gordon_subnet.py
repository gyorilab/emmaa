from os.path import abspath, dirname, join
from indra.tools import assemble_corpus as ac
from indra.databases import hgnc_client
from indra.assemblers.indranet import IndraNetAssembler
from indra.sources import indra_db_rest as idr


if __name__ == '__main__':
    stmts_path = join(dirname(abspath(__file__)), '..', '..', '..',
                             'covid-19', 'stmts')
    gordon_stmts_path = join(stmts_path, 'gordon_ndex_stmts.pkl')

    gordon_stmts = ac.load_statements(gordon_stmts_path)

    # Get human interactors of viral proteins from Gordon et al.
    hgnc_ids = [ag.db_refs['HGNC'] for stmt in gordon_stmts
                for ag in stmt.agent_list()
                if ag is not None and 'HGNC' in ag.db_refs]
    hgnc_names = [hgnc_client.get_hgnc_name(id) for id in hgnc_ids]

    stmts = []
    for gene in hgnc_names:
        idrp = idr.get_statements(agents=[gene])
        stmts.extend(idrp.statements)

    ac.dump_statements(stmts, 'gordon_ppi_stmts.pkl')
