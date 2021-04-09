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
        The list of search terms that led to the creation of the Statement.
    metadata : dict
        Additional metadata for the statement.
    """
    def __init__(self, stmt, date, search_terms, metadata=None):
        self.stmt = stmt
        self.date = date
        self.search_terms = search_terms
        self.metadata = metadata if metadata else {}

    def __repr__(self):
        return '%s(%s, %s, %s)' % (self.__class__.__name__, self.stmt,
                                   self.date, self.search_terms)

    def to_json(self):
        output_json = emmaa_metadata_json(self.search_terms, self.date,
                                          self.metadata)
        # Get json representation of statement
        json_stmt = self.stmt.to_json(use_sbo=False)
        # Stringify source hashes: JavaScript can't handle int's of length > 16
        for ev in json_stmt['evidence']:
            ev['source_hash'] = str(ev['source_hash'])
        output_json['stmt'] = json_stmt
        return output_json


def to_emmaa_stmts(stmt_list, date, search_terms, metadata=None):
    """Make EMMAA statements from INDRA Statements with the given metadata."""
    emmaa_stmts = []
    ann = emmaa_metadata_json(search_terms, date, metadata)
    for indra_stmt in stmt_list:
        add_emmaa_annotations(indra_stmt, ann)
        es = EmmaaStatement(indra_stmt, date, search_terms, metadata)
        emmaa_stmts.append(es)
    return emmaa_stmts


def emmaa_metadata_json(search_terms, date, metadata):
    if not metadata:
        metadata = {}
    return {'search_terms': [st.to_json() for st in search_terms],
            'date': date.strftime('%Y-%m-%d-%H-%M-%S'),
            'metadata': metadata}


def add_emmaa_annotations(indra_stmt, annotation):
    for evid in indra_stmt.evidence:
        evid.annotations['emmaa'] = annotation


def filter_emmaa_stmts_by_tag(estmts, allowed_tags=['internal']):
    estmts_out = []
    for estmt in estmts:
        if estmt.source_tag in allowed_tags:
            estmts_out.append(estmt)
    return estmts_out


def filter_indra_stmts_by_tag(stmts, allowed_tags=['internal']):
    stmts_out = []
    for stmt in stmts:
        evid_tags = set()
        for evid in stmt.evidence:
            if evid.annotations.get('emmaa'):
                evid_tags.add(evid.annotations['emmaa']['source_tag'])
        if any([tag in allowed_tags for tag in evid_tags]):
            stmts_out.append(stmt)
    return stmts_out
