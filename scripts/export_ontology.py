import json
import gzip
import networkx
from indra.databases import uniprot_client
from indra.ontology.bio import bio_ontology


def is_human_protein(bio_ontology, node):
    if bio_ontology.get_ns(node) in {'HGNC', 'FPLX'}:
        return True
    elif bio_ontology.get_ns(node) == 'UP' and \
            uniprot_client.is_human(bio_ontology.get_id(node)):
        return True
    return False


def is_non_human_protein(bio_ontology, node):
    if bio_ontology.get_ns(node) == 'UP' and \
             not uniprot_client.is_human(bio_ontology.get_id(node)):
        return True
    return False


def add_protein_parents(bio_ontology):
    human_root = 'INDRA:HUMAN_PROTEIN'
    non_human_root = 'INDRA:NON_HUMAN_PROTEIN'
    bio_ontology.add_node(human_root, name='Human protein')
    bio_ontology.add_node(non_human_root, name='Non-human protein')
    edges_to_add = []
    for node in bio_ontology.nodes():
        if is_human_protein(bio_ontology, node):
            edges_to_add.append((node, human_root, {'type': 'isa'}))
        elif is_non_human_protein(bio_ontology, node):
            edges_to_add.append((node, non_human_root, {'type': 'isa'}))
    bio_ontology.add_edges_from(edges_to_add)


if __name__ == '__main__':
    bio_ontology.initialize()
    add_protein_parents(bio_ontology)
    node_link = networkx.node_link_data(bio_ontology)
    fname = 'bio_ontology_v%s.json.gz' % bio_ontology.version
    with gzip.open(fname, 'wb') as fh:
        fh.write(json.dumps(node_link, indent=1).encode('utf-8'))
