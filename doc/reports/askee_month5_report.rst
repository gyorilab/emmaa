ASKE-E Month 5 Milestone Report
===============================

Semantic filters to improve model analysis
------------------------------------------


Model analysis exploiting ontological relationships
---------------------------------------------------
We extended the way EMMAA models are tested against the set of experimental
observations. In the past we were only finding the paths between the entities
provided in the tests. The limitation of this approach is that we could only
return a path if exact matches of test entities were present in the model and
if there was a path between them. In the new approach we allow the paths to
be found between more specific versions of test entities (e.g. a member of
a protein family is a more specific version of a family entity; an entity with
modification (e.g. phosphorylated gene) is a more specific version of the same
entity without modification, etc.). We use the INDRA ontology to map between
generic and specific versions of entities. This information is used to
determine which tests can be applied to the model and to find the paths. If the
path found starts or ends with a more specific version of a test entity, we
add a special "is a refinement of" or "has a refinement" edge to the path.

Improved reading and assembly of protein chains and fragments
-------------------------------------------------------------
Protein chains and fragments are important both for human and
viral biology. In ASKE-E month 2, we reported having extended the Reach reading
system with lexicalizations of these entities from UniProt and the Protein
Ontology (PR). This month, we made a number of extensions to our software
stack to propagate these extensions in a useful way.

First, UniProt and PR have a large number of overlapping entries but neither
source provides mappings to the other at the level of protein chains (only full
protein entries). We developed a semi-automated approach to find and curate
these mappings. We used `Gilda <https://github.com/indralab/gilda>`_ to find
lexical overlaps between the two ontologies and put these as predictions into
the `Biomappings repository and curation tool
<https://github.com/biomappings/biomappings>`.

Bio ontology optimized for visualization
----------------------------------------
We implemented a custom export of the INDRA BioOntology graph that is optimized
for organizing nodes in a UI. The idea is to create top-level groups of
entities that correspond to an intuitive category (e.g., human genes/proteins,
non-human genes/proteins, small molecules, diseases, etc.). EMMAA models
don't contain this information about their entities directly, rather, they
are inferred from identifiers assigned to each entity in a given set of
name spaces. However, some name spaces contain multiple types of entities
(e.g., MESH contains small molecules as well as diseases) and some entity
types are distributed across multiple name spaces (e.g., human genes/proteins
can be grounded to HGNC, UniProt, FamPlex, etc.). In this custom export,
we split some name spaces and merged others to create a more ideal resolution
and shared this export with the Uncharted team.
