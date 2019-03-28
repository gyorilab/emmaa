"""This module contains classes to generate prior networks."""


class SearchTerm(object):
    """Represents a search term to be used in a model configuration.

    Parameters
    ----------
    type : str
        The type of search term, e.g. gene, bioprocess, other
    name : str
        The name of the search term, is equivalent to an Agent name
    db_refs : dict
        A dict of database references for the given term, is similar
        to an Agent db_refs dict
    search_term : str
        The actual search term to us for searching PubMed
    """
    def __init__(self, type, name, db_refs, search_term):
        self.type = type
        self.name = name
        self.db_refs = db_refs
        self.search_term = search_term

    def __str__(self):
        return f'SearchTerm({self.type}, {self.name})'

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.type, self.name, tuple(sorted(self.db_refs.items())),
                     self.search_term))

    def to_json(self):
        """Return search term as JSON."""
        jd = {'type': self.type,
              'name': self.name,
              'db_refs': self.db_refs,
              'search_term': self.search_term}
        return jd

    @classmethod
    def from_json(cls, jd):
        """Return a SearchTerm object from JSON."""
        return SearchTerm(**jd)

    def __eq__(self, other):
        return self.type == other.type and self.name == other.name and \
            self.db_refs == other.db_refs and \
            self.search_term == other.search_term


def get_drugs_for_gene(stmts, hgnc_id):
    """Get list of drugs that target a gene

    Parameters
    ----------
    stmts : list of :py:class:`indra.statements.Statement`
        List of INDRA statements with a drug as subject
    hgnc_id : str
        HGNC id for a gene

    Returns
    -------
    drugs_for_gene : list of :py:class:`emmaa.priors.SearchTerm`
        List of search terms for drugs targeting the input gene
    """
    drugs_for_gene = []
    for stmt in stmts:
        if stmt.obj.db_refs.get('HGNC') == hgnc_id:
            term = SearchTerm(type='drug', name=stmt.subj.name,
                              db_refs=stmt.subj.db_refs,
                              search_term=f'"{stmt.subj.name}"')
            drugs_for_gene.append(term)
    return drugs_for_gene
