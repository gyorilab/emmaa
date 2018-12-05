"""This module contains classes to generate prior networks."""
from collections import OrderedDict


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

    def to_json(self):
        """Return search term as JSON."""
        jd = OrderedDict()
        jd['type'] = self.type
        jd['name'] = self.name
        jd['db_refs'] = self.db_refs
        jd['search_term'] = self.search_term
        return jd

    def __eq__(self, other):
        return self.type == other.type and self.name == other.name and \
            self.db_refs == other.db_refs and \
            self.search_term == other.search_term
