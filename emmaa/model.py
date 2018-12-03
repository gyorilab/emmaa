from indra.literature import pubmed_client


class EmmaaStatement(object):
    def __init__(self, stmt, date, search_terms):
        self.stmt = stmt
        self.date = date
        self.search_terms = search_terms


class EmmaaModel(object):
    def __init__(self, config):
        self.stmts = []
        self.search_terms = []
        self.ndex_network = None
        self._load_config(config)

    def add_statements(self, stmts):
        self.stmts += stmts

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