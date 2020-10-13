from indra.tools import assemble_corpus as ac


filter_functions = {}


def register_filter(function):
    """
    Decorator to register a function as a filter for tests.

    A function should take an agent as an argument and return True if the agent
    is allowed to be in a path and False otherwise.
    """
    filter_functions[function.__name__] = function
    return function


@register_filter
def filter_chem_mesh_go(agent):
    gr = agent.get_grounding()
    if gr[0] in ['MESH', 'CHEBI', 'GO']:
        return False
    return True
