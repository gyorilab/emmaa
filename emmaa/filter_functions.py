from indra.tools import assemble_corpus as ac


node_filter_functions = {}
edge_filter_functions = {}


def register_filter(filter_type):
    """Decorator to register node or edge filter functions.

    A node filter function should take an agent as an argument and return True
    if the agent is allowed to be in a path and False otherwise.

    An edge filter function should take three (graph, source, target - for
    DiGraph) or three (graph, source, target, key -  for MultiDiGraph)
    parameters and return True if the edge should be in the graph and False
    otherwise.
    """
    def register(function):
        if filter_type == 'node':
            func_dict = node_filter_functions
        elif filter_type == 'edge':
            func_dict = edge_filter_functions
        func_dict[function.__name__] = function
        return function
    return register


@register_filter('node')
def filter_chem_mesh_go(agent):
    """Filter ungrounded agents and agents grounded to MESH, CHEBI, GO unless
    also grounded to HMDB.
    """
    gr = agent.get_grounding()
    return gr[0] not in {'MESH', 'CHEBI', 'GO', None}


@register_filter('edge')
def filter_to_internal_edges(g, u, v, *args):
    """Return True if an edge is internal. NOTE it returns True if any of the
    statements associated with an edge is internal.
    """
    if args:
        edge = g[u][v][args[0]]
    else:
        edge = g[u][v]
    for stmts_dict in edge['statements']:
        if stmts_dict['internal']:
            return True
    return False
