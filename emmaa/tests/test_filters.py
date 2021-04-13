import networkx as nx
from emmaa.filter_functions import filter_chem_mesh_go, \
    filter_to_internal_edges
from indra.statements import Agent
from indra.explanation.pathfinding import get_subgraph

edges = [
    (1, 2, {'statements': [{'internal': True}]}),
    (2, 3, {'statements': [{'internal': False}]}),
    (3, 4, {'statements': [{'internal': True}, {'internal': True}]}),
    (4, 5, {'statements': [{'internal': True}, {'internal': False}]}),
    (5, 6, {'statements': [{'internal': False}, {'internal': False}]}),
]
g = nx.DiGraph()
g.add_edges_from(edges)


def test_filter_to_internal():
    assert filter_to_internal_edges(g, 1, 2)
    assert not filter_to_internal_edges(g, 2, 3)
    assert filter_to_internal_edges(g, 3, 4)
    assert filter_to_internal_edges(g, 4, 5)  # enough to have one internal
    assert not filter_to_internal_edges(g, 5, 6)


def test_internal_subgraph():
    new_g = get_subgraph(g, filter_to_internal_edges)
    assert isinstance(new_g, nx.DiGraph)
    assert len(new_g.edges) == 3
    assert (2, 3) not in new_g.edges
    assert (5, 6) not in new_g.edges
    assert (4, 5) in new_g.edges


def test_filter_chem_mesh_go():
    a = Agent('A', db_refs={'HGNC': '1234'})
    b = Agent('B', db_refs={'CHEBI': '2345'})
    c = Agent('C', db_refs={'MESH': '3456'})
    d = Agent('D', db_refs={'GO': '4567'})
    e = Agent('E', db_refs={'CHEBI': '5678', 'HGNC': '6789'})
    assert filter_chem_mesh_go(a)
    assert not filter_chem_mesh_go(b)
    assert not filter_chem_mesh_go(c)
    assert not filter_chem_mesh_go(d)
    # Decision made based on default namespace order
    assert filter_chem_mesh_go(e)
