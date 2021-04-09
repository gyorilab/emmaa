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


def filter_emmaa_stmts_by_metadata(estmts, conditions):
    estmts_out = []
    for estmt in estmts:
        checks = []
        for key, value in conditions.items():
            checks.append(estmt.metadata.get(key) == value)
        if all(checks):
            estmts_out.append(estmt)
    return estmts_out


def filter_indra_stmts_by_metadata(stmts, conditions, evid_policy='any'):
    stmts_out = []
    for stmt in stmts:
        add = check_stmt(stmt, conditions, evid_policy)
        if add:
            stmts_out.append(stmt)
    return stmts_out


def check_stmt(stmt, conditions, evid_policy='any'):
    evid_checks = []
    for evid in stmt.evidence:
        emmaa_anns = evid.annotations.get('emmaa')
        if emmaa_anns:
            metadata = emmaa_anns.get('metadata')
            checks = []
            for key, value in conditions.items():
                checks.append(metadata[key] == value)
            evid_checks.append(all(checks))
            if all(checks) and evid_policy == 'any':
                break
    if evid_policy == 'any':
        return any(evid_checks)
    elif evid_policy == 'all':
        return all(evid_checks)


def is_internal(stmt):
    return check_stmt(stmt, {'internal': True}, evid_policy='any')
