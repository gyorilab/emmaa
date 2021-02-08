"""This script generates a custom export of the INDRA Ontology
graph with additional nodes to group entities."""
import json
import gzip
import pandas
import networkx
from collections import defaultdict
from indra.databases import uniprot_client
from indra.ontology.bio import bio_ontology
from indra.resources import get_resource_path


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
    for category_name, category_label in category_map.items():
        bio_ontology.add_node(category_label, name=category_name)
        edges_to_add.append((category_label, human_root, {'type': 'isa'}))

    for node in bio_ontology.nodes():
        if is_human_protein(bio_ontology, node):
            category_node = get_category(node)
            if not category_node:
                edges_to_add.append((node, human_root, {'type': 'isa'}))
            else:
                edges_to_add.append((node, category_node, {'type': 'isa'}))
        elif is_non_human_protein(bio_ontology, node):
            edges_to_add.append((node, non_human_root, {'type': 'isa'}))
    bio_ontology.add_edges_from(edges_to_add)


def get_category(node):
    name = bio_ontology.get_name(*bio_ontology.get_ns_id(node))
    category = categories.get(name)
    if category:
        category_node = category_map[category]
        return category_node
    return None


def _process_categories():
    idg_df = pandas.read_csv('IDG_target_final.csv')
    tf_df = pandas.read_csv(get_resource_path('transcription_factors.csv'))
    pp_df = pandas.read_csv(get_resource_path('phosphatases.tsv'), sep='\t',
                            header=None)
    categories = {}
    for _, row in idg_df.iterrows():
        categories[row['gene']] = row['idgFamily']

    for _, row in tf_df.iterrows():
        categories[row[1]] = 'Transcription factor'

    for _, row in pp_df.iterrows():
        categories[row[0]] = 'Phosphatase'
    return categories


categories = _process_categories()

category_map = {
    'Kinase': 'INDRA:KINASE',
    'GPCR': 'INDRA:GPCR',
    'Ion Channel': 'INDRA:ION_CHANNEL',
    'Transcription factor': 'INDRA:TRANSCRIPTION_FACTOR',
    'Phosphatase': 'INDRA:PHOSPHATASE',
}


if __name__ == '__main__':
    bio_ontology.initialize()
    add_protein_parents(bio_ontology)
    node_link = networkx.node_link_data(bio_ontology)
    fname = 'bio_ontology_v%s.json.gz' % bio_ontology.version
    with gzip.open(fname, 'wb') as fh:
        fh.write(json.dumps(node_link, indent=1).encode('utf-8'))
