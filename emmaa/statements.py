class EmmaaStatement(object):
    """Represents an EMMAA Statement.

    Parameters
    ----------
    stmt : indra.statements.Statement
        An INDRA Statement
    date : datetime
        A datetime object that is attached to the Statement. Typically represnts
        the time at which the Statement was created.
    search_terms
        The set of search terms that lead to the creation of the Sttement.

    """
    def __init__(self, stmt, date, search_terms):

        self.stmt = stmt
        self.date = date
        self.search_terms = search_terms