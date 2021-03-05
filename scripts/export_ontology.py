"""This script generates a custom export of the INDRA Ontology
graph with additional nodes to group entities."""
import json
import gzip
import boto3
import pandas
import networkx
from indra.databases import uniprot_client, mesh_client
from indra.ontology.bio import bio_ontology, BioOntology
from indra.resources import get_resource_path


def is_human_protein(bio_ontology, node):
    """Return True if the given ontology node is a human protein."""
    if bio_ontology.get_ns(node) == 'HGNC':
        return True
    elif bio_ontology.get_ns(node) == 'UP' and \
            uniprot_client.is_human(bio_ontology.get_id(node)):
        return True
    return False


def is_protein_family(bio_ontology, node):
    """Return True if the given ontology node is a protein family."""
    if bio_ontology.get_ns(node) == 'FPLX':
        return True
    return False


def has_fplx_parents(bio_ontology, node):
    """Return True if the given ontology node has FamPlex parents."""
    parents = bio_ontology.get_parents(*bio_ontology.get_ns_id(node))
    if any(p[0] == 'FPLX' for p in parents):
        return True
    return False


def is_non_human_protein(bio_ontology, node):
    """Return True if the given ontology node is a non-human protein."""
    if bio_ontology.get_ns(node) == 'UP' and \
             not uniprot_client.is_human(bio_ontology.get_id(node)):
        return True
    return False


def is_mesh_subroot_node(bio_ontology, node):
    ns, id = bio_ontology.get_ns_id(node)
    if ns == 'MESH':
        tree_numbers = mesh_client.get_mesh_tree_numbers(id)
        if len(tree_numbers) == 1 and '.' not in tree_numbers[0]:
            return tree_numbers[0][0]
    return None


def add_mesh_parents(bio_ontology: BioOntology):
    """Add missing root level nodes to the MeSH ontology."""
    for letter, name in mesh_roots_map.items():
        bio_ontology.add_node(bio_ontology.label('MESH', letter), name=name)

    edges_to_add = []
    for node in bio_ontology.nodes():
        # First deal with subtree root nodes
        subtree = is_mesh_subroot_node(bio_ontology, node)
        if subtree is not None:
            edges_to_add.append((
                node,
                bio_ontology.label('MESH', subtree),
                {'type': 'isa'}
            ))
        db_ns, db_id = bio_ontology.get_ns_id(node)
        # Then deal with supplementary concepts
        if db_ns == 'MESH' and db_id.startswith('C') \
                and db_id != 'C':  # To skip the previously added subroot node
            edges_to_add.append((
                node,
                bio_ontology.label('MESH', 'S'),
                {'type': 'isa'}
            ))
    bio_ontology.add_edges_from(edges_to_add)


def add_chebi_parents(bio_ontology: BioOntology):
    """Add missing root level nodes to the ChEBI ontology."""
    chebi_root = bio_ontology.label('CHEBI', 'CHEBI:0')
    bio_ontology.add_node(chebi_root, name='small molecule')
    edges_to_add = []
    for node in {'CHEBI:CHEBI:24431', 'CHEBI:CHEBI:36342',
                 'CHEBI:CHEBI:50906'}:
        edges_to_add.append((node, chebi_root, {'type': 'isa'}))
    bio_ontology.add_edges_from(edges_to_add)


def add_protein_parents(bio_ontology):
    """Add parent categories for proteins in the ontology."""
    # Add root nodes for human and non-human proteins
    human_root = 'INDRA:HUMAN_PROTEIN'
    non_human_root = 'INDRA:NON_HUMAN_PROTEIN'
    bio_ontology.add_node(human_root, name='Human protein')
    bio_ontology.add_node(non_human_root, name='Non-human protein')

    # We add each category as a node and link them to the human protein
    # root
    edges_to_add = []
    for category_name, category_label in category_map.items():
        bio_ontology.add_node(category_label, name=category_name)
        edges_to_add.append((category_label, human_root, {'type': 'isa'}))

    # Now we go over the whole ontology, and add extra edges
    for node in bio_ontology.nodes():
        # If this is a protein family and doesn't have any further FamPlex
        # parents then we find its specific protein children, look at all
        # their categories, and add links from this node to the nodes of
        # these categories.
        if is_protein_family(bio_ontology, node):
            # Skip if this has further FPLX parents
            if has_fplx_parents(bio_ontology, node):
                continue
            else:
                # Get child categories
                categoriesx = get_categories(node)
                # If there are no categories, link directly to human protein
                # root
                if not categoriesx:
                    edges_to_add.append((node, human_root, {'type': 'isa'}))
                else:
                    # If there are categories, we link this family to each
                    # of those
                    for category in categoriesx:
                        edges_to_add.append((node, category_map[category],
                                             {'type': 'isa'}))
        # If this is a specific human protein and doesn't have any FamPlex
        # parents then we link it to either a category node or the root node
        elif is_human_protein(bio_ontology, node):
            if has_fplx_parents(bio_ontology, node):
                continue
            category_node = get_category(node)
            # If there is a caqtegory, we link to that, otherwise to
            # the human protein root
            if not category_node:
                edges_to_add.append((node, human_root, {'type': 'isa'}))
            else:
                edges_to_add.append((node, category_node, {'type': 'isa'}))
        elif is_non_human_protein(bio_ontology, node):
            edges_to_add.append((node, non_human_root, {'type': 'isa'}))
    bio_ontology.add_edges_from(edges_to_add)


def get_category(node):
    """Return a category label for a given specific protein ontology node."""
    name = bio_ontology.get_name(*bio_ontology.get_ns_id(node))
    category = categories.get(name)
    if category:
        category_node = category_map[category]
        return category_node
    return None


def get_categories(fplx_node):
    """Return category labels for a given protein family ontology node."""
    children = bio_ontology.get_children(*bio_ontology.get_ns_id(fplx_node),
                                         ns_filter='HGNC')
    children_names = {bio_ontology.get_name(*ch) for ch in children}
    child_categories = {categories[name] for name in children_names
                        if name in categories}
    return child_categories


def _process_categories():
    """Collect protein category labels from multiple sources."""
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


def map_node_names(bio_ontology, rename_map):
    for node_label, new_name in rename_map.items():
        bio_ontology.nodes[node_label]['name'] = rename_map


categories = _process_categories()

category_map = {
    'Kinase': 'INDRA:KINASE',
    'GPCR': 'INDRA:GPCR',
    'Ion Channel': 'INDRA:ION_CHANNEL',
    'Transcription factor': 'INDRA:TRANSCRIPTION_FACTOR',
    'Phosphatase': 'INDRA:PHOSPHATASE',
}


mesh_roots_map = {
    'A': 'Anatomy',
    'B': 'Organisms',
    'C': 'Diseases',
    'D': 'Chemicals and Drugs',
    'E': 'Analytical, Diagnostic and Therapeutic Techniques, and Equipment',
    'F': 'Psychiatry and Psychology',
    'G': 'Phenomena and Processes',
    'H': 'Disciplines and Occupations',
    'I': 'Anthropology, Education, Sociology, and Social Phenomena',
    'J': 'Technology, Industry, and Agriculture',
    'K': 'Humanities',
    'L': 'Information Science',
    'M': 'Named Groups',
    'N': 'Health Care',
    'V': 'Publication Characteristic',
    'Z': 'Geographicals',
    # This is added manually for supplementary concepts, it's not a real
    # sub-tree letter
    'S': 'Supplementary Concept'
}

rename_map = {
    'HP:HP:0000001': 'Human phenotype',
    'CHEBI:CHEBI:24431': 'chemicals by structure',
    'CHEBI:CHEBI:50906': 'chemicals by role',
}


if __name__ == '__main__':
    export_version = '1'
    bio_ontology.initialize()
    add_protein_parents(bio_ontology)
    add_mesh_parents(bio_ontology)
    add_chebi_parents(bio_ontology)
    map_node_names(bio_ontology, rename_map)
    node_link = networkx.node_link_data(bio_ontology)
    fname = 'bio_ontology_v%s_export_v%s.json.gz' % \
        (bio_ontology.version, export_version)
    with gzip.open(fname, 'wb') as fh:
        fh.write(json.dumps(node_link, indent=1).encode('utf-8'))
    # S3 upload
    s3 = boto3.client('s3')
    print('Uploading to S3')
    with open(fname, 'rb') as fh:
        s3.put_object(Body=fh.read(),
                      Bucket='emmaa',
                      Key=f'integration/ontology/{fname}',
                      ACL='public-read')
