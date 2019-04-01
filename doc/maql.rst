Model Analysis Query Language
=============================

This is a specification for a machine-readable description format for
the analysis and querying of EMMAA models. The specification uses a JSON
format that is easily generated and processed, and is also human-readable
and editable.

The specification extends to four, increasingly complex query types:
- Structural properties with constraints
- Path properties with constraints
- Simple intervention properties
- Comparative intervention properties

Note that the specification for *defining* queries does not explcitly specify
the method by which the query is executed, though some query specifications are
defined with a certain type of analysis method in mind.

Structural properties with constraints
--------------------------------------
Structural properties of models are evaluated directly at the knowledge-level,
in our case at the level of INDRA Statements. Each Statement has a type
(Activation, Dephosphorylation, etc.), refers to one or more entities (Agents)
as arguments, which themselves can have different types are determined by
grounding to an ontology. At an abstract level

Structural property queries can have different "topologies" in terms of the
entities they reference including (i) unary queries referring to a single
Agent alone, (ii) queries referring to a single Agent and its neighborhood,
(iii) binary queries that refer to two Agents.

Structural property queries may also constrain the type of the Statement and
Agent.

Specifying topology
~~~~~~~~~~~~~~~~~~~
Structural queries have multiple subtypes based on the topology of the query:
- binary_directed: specifies two Agents, a *source* and a *target*, between
  which, a directed relationship is queried.
- binary_undirected: specifies two Agents in an *agents* list, in arbitrary
  order, and relationship direction is of interest in the query.
- neighborhood: specifies a single *agent* around which a relationship in
  any direction (incoming, outgoing, undirected) is of interest.
- to_target: specifies a single Agent as a *target* and only incoming
  relationships are of interest.
- from_source: specifies a single Agent as a *source* and only outgoing
  relationships are of interest.
- single_agent: specifies a single *agent* with the query focusing on a
  property of the Agent itself rather than any relationships.

Each Agent is defined via its name, and optionally, groundings, for more
information, see the relevant entry of the INDRA JSON Schema:
https://github.com/sorgerlab/indra/blob/master/indra/resources/statements_schema.json#L77

Entity constraints
~~~~~~~~~~~~~~~~~~
Entity constraints (*entity_constraints*) can be added to the query,
these can constrain the *type* (protein, chemical, biological process, etc.)
and *subtype* (kinase, transcription factor, etc.) of the Agents of interest.

Relationship constraints
~~~~~~~~~~~~~~~~~~~~~~~~
Relationship constraints can be specified by describing the *type* of Statement
establishing the relatonship.

Examples
~~~~~~~~

Example: "What kinases does BRAF phosphorylate?"

.. code-block:: json

    {"type": "from_source",
     "source": {
        "type": "agent",
        "name": "BRAF"
        },
     "entity_constraints": [
        {"type": "protein",
         "subtype": "kinase"}
        ],
     "relationship_constraints": [
       {"type": "Phosphorylation"}
       ]
     }


Path properties with constraints
