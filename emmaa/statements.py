import logging


logger = logging.getLogger(__name__)


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
    logger.info(f'Making {len(stmt_list)} EMMAA statements with metadata: '
                f'{metadata}')
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
    """Add EMMAA annotations to inner INDRA statement."""
    for evid in indra_stmt.evidence:
        evid.annotations['emmaa'] = annotation


def filter_emmaa_stmts_by_metadata(estmts, conditions):
    """Filter EMMAA statements to those where conditions are met.

    Parameters
    ----------
    estmts : list[emmaa.statements.EmmaaStatement]
        A list of EMMAA Statements to filter.
    conditions : dict
        Conditions to filter on represented as key-value pairs that statements'
        metadata can be compared to. NOTE if there are multiple conditions
        provided, the function will require that all conditions are met
        to keep a statement.

    Returns
    -------
    estmts_out : list[emmaa.statements.EmmaaStatement]
        A list of EMMAA Statements which meet the conditions.
    """
    logger.info(f'Filtering {len(estmts)} EMMAA Statements with the following'
                f' conditions: {conditions}')
    estmts_out = []
    for estmt in estmts:
        # Not filter out "old version" statements without metadata
        if not hasattr(estmt, 'metadata'):
            estmts_out.append(estmt)
            continue
        checks = []
        # Collect results for all conditions
        for key, value in conditions.items():
            checks.append(estmt.metadata.get(key) == value)
        # Only keep statements meeting all conditions
        if all(checks):
            estmts_out.append(estmt)
    logger.info(f'Got {len(estmts_out)} EMMAA Statements after filtering')
    return estmts_out


def filter_indra_stmts_by_metadata(stmts, conditions, evid_policy='any'):
    """Filter INDRA statements to those where conditions are met.

    Parameters
    ----------
    stmts : list[indra.statements.Statement]
        A list of INDRA Statements to filter.
    conditions : dict
        Conditions to filter on represented as key-value pairs that statements'
        metadata can be compared to. NOTE if there are multiple conditions
        provided, the function will require that all conditions are met
        to keep a statement.
    evid_policy : str
        Policy for checking statement's evidence objects. If 'all', then the
        statement is kept only if all of it's evidence objects meet the
        conditions. If 'any', the statement is kept as long as at least one
        of its evidences meets the conditions.

    Returns
    -------
    stmts_out : list[indra.statements.Statement]
        A list of INDRA Statements which meet the conditions.
    """
    logger.info(f'Filtering {len(stmts)} INDRA Statements with the following'
                f' conditions: {conditions} in {evid_policy} evidence')
    stmts_out = []
    for stmt in stmts:
        add = check_stmt(stmt, conditions, evid_policy)
        if add:
            stmts_out.append(stmt)
    logger.info(f'Got {len(stmts_out)} INDRA Statements after filtering')
    return stmts_out


def check_stmt(stmt, conditions, evid_policy='any'):
    """Decide whether a statement meets the conditions.

    Parameters
    ----------
    stmt : indra.statements.Statement
        INDRA Statement that should be checked for conditions.
    conditions : dict
        Conditions represented as key-value pairs that statements'
        metadata can be compared to. NOTE if there are multiple conditions
        provided, the function will require that all conditions are met to
        return True.
    evid_policy : str
        Policy for checking statement's evidence objects. If 'all', then the
        function returns True only if all of statement's evidence objects meet
        the conditions. If 'any', the function returns True as long as at
        least one of statement's evidences meets the conditions.

    Return
    ------
    meets_conditions : bool
        Whether the Statement meets the conditions.
    """
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
    # There are no evidence checks if stmt doesn't have emmaa annotations,
    # in this case we say it meets conditions by default
    if not evid_checks:
        return True
    # Make decision based on the evidence policy
    if evid_policy == 'any':
        return any(evid_checks)
    elif evid_policy == 'all':
        return all(evid_checks)


def is_internal(stmt):
    """Check if statement has any internal evidence."""
    return check_stmt(stmt, {'internal': True}, evid_policy='any')
