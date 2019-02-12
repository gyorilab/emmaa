class EmmaaStatement(object):
    """Represents an EMMAA Statement.

    Parameters
    ----------
    stmt : indra.statements.Statement
        An INDRA Statement
    date : datetime
        A datetime object that is attached to the Statement. Typically
        represents the time at which the Statement was created.
    search_terms : list[emmaa.priors.SearchTerm]
        The slist of search terms that led to the creation of the Statement.
    """
    def __init__(self, stmt, date, search_terms):
        self.stmt = stmt
        self.date = date
        self.search_terms = search_terms

    def __repr__(self):
        return '%s(%s, %s, %s)' % (self.__class__.__name__, self.stmt,
                                   self.date, self.search_terms)

    def to_json(self, use_sbo=False):
        output_json = {'search_terms': self.search_terms,
                       'date': self.date.strftime('%Y-%m-%d-%H-%M-%S')}
        # Get json representation of statement
        json_stmt = self.stmt.to_json(use_sbo=use_sbo)
        # Stringify source hashes: JavaScript can't handle int's of length > 16
        for ev in json_stmt['evidence']:
            ev['source_hash'] = str(ev['source_hash'])
        output_json['stmt'] = json_stmt
        return output_json
