import datetime
from copy import deepcopy

from emmaa.statements import EmmaaStatement, to_emmaa_stmts, \
    filter_emmaa_stmts_by_metadata, filter_indra_stmts_by_metadata
from emmaa.priors import SearchTerm
from indra.statements import Activation, Agent, Evidence


braf = Agent('BRAF', db_refs={'HGNC': '1097'})
map2k1 = Agent('MAP2K1', db_refs={'HGNC': '6840'})
stmt = Activation(braf, map2k1,
                  evidence=[Evidence(text='BRAF activates MAP2K1.',
                            source_api='assertion',
                            text_refs={'TRID': '1234'})])
date = datetime.datetime.now()
search_terms = [
    SearchTerm('gene', braf.name, braf.db_refs, '"BRAF"'),
    SearchTerm('gene', map2k1.name, map2k1.db_refs, '"MAP2K1"')]


def test_to_emmaa_stmts():
    estmts = to_emmaa_stmts(
        [stmt],
        date=date,
        search_terms=search_terms,
        metadata={'internal': True})
    assert estmts
    estmt = estmts[0]
    assert isinstance(estmt, EmmaaStatement)
    assert estmt.stmt == stmt
    assert estmt.metadata == {'internal': True}
    emmaa_anns = estmt.stmt.evidence[0].annotations.get('emmaa')
    assert emmaa_anns
    assert len(emmaa_anns['search_terms']) == 2
    assert emmaa_anns['metadata'] == {'internal': True}


def test_filter_emmaa_stmts():
    for st in [None, search_terms]:
        estmt1 = EmmaaStatement(stmt, date, st, {'internal': True})
        estmt2 = EmmaaStatement(stmt, date, st, {'internal': False})
        estmt3 = EmmaaStatement(stmt, date, st)
        del estmt3.metadata  # Imitate older style statement without metadata
        # Only estmt2 with internal False should be filtered out
        filtered_estmts = filter_emmaa_stmts_by_metadata(
            [estmt1, estmt2, estmt3], {'internal': True})
        assert len(filtered_estmts) == 2
        assert estmt1 in filtered_estmts
        assert estmt3 in filtered_estmts


def test_filter_indra_stmts():
    def make_stmt_with_evid_anns(internal_list):
        new_stmt = deepcopy(stmt)
        new_stmt.evidence = []
        for internal_val in internal_list:
            new_evid = Evidence(text='BRAF activates MAP2K1.',
                                source_api='assertion',
                                text_refs={'TRID': '1234'})
            if internal_val is None:
                new_evid.annotations = {}
            # True or False
            else:
                new_evid.annotations = {
                    'emmaa': {
                        'metadata': {'internal': internal_val}}}
            new_stmt.evidence.append(new_evid)
        return new_stmt

    stmt1 = make_stmt_with_evid_anns([None, None])  # Not filter unknown anns
    stmt2 = make_stmt_with_evid_anns([True])  # Only true anns
    stmt3 = make_stmt_with_evid_anns([True, True])  # Only true anns
    stmt4 = make_stmt_with_evid_anns([None, True])  # Only true or unknown anns
    stmt5 = make_stmt_with_evid_anns([False, True])  # Mixed true and false
    stmt6 = make_stmt_with_evid_anns([False])  # Only false anns
    stmt7 = make_stmt_with_evid_anns([None, False])  # Filter false or unknown
    stmt8 = make_stmt_with_evid_anns([False, False])  # Only false anns

    stmt9 = make_stmt_with_evid_anns([False])
    del stmt9.evidence[0].annotations["emmaa"]["metadata"]["internal"]

    conditions = {'internal': True}
    stmts = [stmt1, stmt2, stmt3, stmt4, stmt5, stmt6, stmt7, stmt8, stmt9]

    filtered_any = filter_indra_stmts_by_metadata(stmts, conditions, 'any')
    assert len(filtered_any) == 5
    assert stmt6 not in filtered_any
    assert stmt7 not in filtered_any
    assert stmt8 not in filtered_any
    assert stmt9 not in filtered_any
    # Mixed is not filtered
    assert stmt5 in filtered_any

    filtered_all = filter_indra_stmts_by_metadata(stmts, conditions, 'all')
    assert len(filtered_all) == 4
    assert stmt6 not in filtered_all
    assert stmt7 not in filtered_all
    assert stmt8 not in filtered_all
    # Mixed is filtered too here
    assert stmt5 not in filtered_all
