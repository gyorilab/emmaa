from indra.databases import ndex_client
import indra.tools.assemble_corpus as ac
from indra.literature import pubmed_client
from indra.assemblers.cx import CxAssembler


class EmmaaStatement(object):
    def __init__(self, stmt, date, search_terms):
        self.stmt = stmt
        self.date = date
        self.search_terms = search_terms


class EmmaaModel(object):
    def __init__(self, name, config):
        self.name = name
        self.stmts = []
        self.search_terms = []
        self.ndex_network = None
        self._load_config(config)

    def add_statements(self, stmts):
        self.stmts += stmts

    def get_indra_smts(self):
        return [es.stmt for es in self.stmts]

    def _load_config(self, config):
        self.search_terms = config['search_terms']
        self.ndex_network = config['ndex']['network']

    def search_literature(self, date_limit=None):
        term_to_pmids = {}
        for term in self.search_terms:
            pmids = pubmed_client.get_ids(term, reldate=date_limit)
            term_to_pmids[term] = pmids
        pmid_to_terms = {}
        for term, pmids in term_to_pmids.items():
            for pmid in pmids:
                try:
                    pmid_to_terms[pmid].append(term)
                except KeyError:
                    pmid_to_terms[pmid] = [term]
        return pmid_to_terms

    def run_assembly(self):
        stmts = self.get_indra_smts()
        stmts = ac.filter_no_hypothesis(stmts)
        stmts = ac.map_grounding(stmts)
        stmts = ac.map_sequence(stmts)
        stmts = ac.filter_human_only(stmts)
        stmts = ac.run_preassembly(stmts, return_toplevel=False)
        return stmts

    def upload_to_ndex(self):
        assembled_stmts = self.run_assembly()
        cxa = CxAssembler(assembled_stmts, network_name=self.name)
        cxa.make_model()
        cx_str = cxa.print_cx()
        ndex_client.update_network(cx_str, self.ndex_network)
