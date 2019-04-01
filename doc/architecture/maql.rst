.. _maql:

Model Analysis Query Language
=============================

This is v1.0 of a specification for a machine-readable description format for
the analysis and querying of EMMAA models. The specification uses a JSON
format that is easily generated and processed, and is also human-readable
and editable.

The specification extends to four, increasingly complex query types:
- Structural properties with constraints
- Path properties with constraints
- Simple intervention properties
- Comparative intervention properties

Note that this specification for defining queries does not explcitly specify
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
Structural queries have multiple *subtypes* based on the topology of the query:

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

  {"type": "structural_property",
   "subtype": "from_source",
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

Ideas for extension
~~~~~~~~~~~~~~~~~~~
The constraints could be generalized to allow logical formulae over entity
types and relations.

Path properties with constraints
--------------------------------
Path properites of models are evaluated at a lower level than simple
structural properties due to the fact that mechanistic paths need to
be causally consistent (i.e., each step of the path needs to be causally
linked to the next step).

Specifying the overall path
~~~~~~~~~~~~~~~~~~~~~~~~~~~
The overall path specification can be done using the JSON Schema developed
for INDRA Statements (see https://github.com/sorgerlab/indra/blob/master/indra/resources/statements_schema.json).
The *path* is specified via an overall *type*, and, depending on the type,
the appropriate Agent arguments.

Entity constraints
~~~~~~~~~~~~~~~~~~
It is possible to specify constraints on the entities (*entity_constraints*)
appearing along the path, for instance, whether to include or exclude
certain Agents. The keys for these specifications are *include* and
*exclude* respectively.

Relationship constraints
~~~~~~~~~~~~~~~~~~~~~~~~
It is also possible to specify constraints on relationships along the path
(*relationship_constraints*) with the *include* and
*exclude* keys.

Examples
~~~~~~~~
Example: "How does EGFR lead to ERK phosphorylation without including
PI3K or any transcriptional regulation?"

.. code-block:: json

    {"type": "path_property",
     "path": {
        "type": "Phosphorylation",
        "enz": {
            "type": "Agent",
            "name": "EGFR"
            },
        "sub": {
            "type": "Agent",
            "name": "ERK"
            }
        },
      "entity_constraints": {
        "exclude": [
            {"type": "Agent",
             "name": "PI3K"}
            ]
        },
      "relationship_constratints": {
        "exclude": [
            {"type": "IncreaseAmount"},
            {"type": "DecreaseAmount"}
            ]
        }
     }

Simple intervention properties
------------------------------
Simple intervention properties focus on the effects of targeted interventions
on one or more entities in the model without considering comparisons or
optimization across multiple interventions.

Specifying an intervention
~~~~~~~~~~~~~~~~~~~~~~~~~~
An intervention can be specified either on a single entity readout or on a
path-level effect (we call this a *reference*, i.e., something that the
intervention is meant to change). In the first case, the readout is
represented, again, as an INDRA Agent, with name, grounding and state. In the
second case, a path is represented as and INDRA Statement with type and Agent
arguments.  The intervention itself is represented as a list of Agents with
additional parameters to specify the type of intervetion.

Specifying the reference
~~~~~~~~~~~~~~~~~~~~~~~~
The *reference* can either have *type* of  *relationship* or *entity*. In case
of a *relationship*, the specification is an INDRA Statement JSON. In case
of an *entity*, the specificaton is an INDRA Agent JSON (see references above).

Specifying the intervetion
~~~~~~~~~~~~~~~~~~~~~~~~~~
The *intervention* consists of a list of intervening entities (specified as
INDRA Agent JSONs) and the perturbation by which the intervention applies to
these entities (i.e., *increase*, *decrease*).

Examples
~~~~~~~~
Example: "How does Selumetinib affect phosphorylated MAPK1?"

.. code-block:: json

    {"type": "simple_intervention_property",
     "reference": {
        "type": "Agent",
        "name": "MAPK1",
        "mods": [
            {"mod_type": "phosphorylation"}
            ]
        },
    "intervention": [
        {"entity": {
            "type": "Agent",
            "name": "Selumetinib"
            },
         "perturbation": "increase"
         }
        ]
     }


Comparative intervention properties
-----------------------------------
Comparative intervention properties are similar to simple intervention
properties but are more general in that they can be used to express
comparisons or optimality among a set of possible intervetions.
The specification consists, again, of a *reference*, but this time, a list
of *interventions* rather than a single *intervention*. The comparison
also needs to be specified, i.e., whether the intervetion is meant to
*increase* or *decrease* the *reference*.

For comparative intervention properties, the *reference* and each possible
*intervention* is specified as above.

Examples
~~~~~~~~
Example: "Is Selumetinib or Vemurafenib optimal in decreasing ERK activation by
EGF?"

.. code-block:: json

    {"type": "comparative_intervention_property",
     "reference": {
        "type": "Activation",
        "subj": {
            "name": "EGF",
            },
        "obj": {
            "name": "ERK",
            }
        },
    "interventions": [
        [{"entity": {
            "type": "Agent",
            "name": "Selumetinib"
            },
         "perturbation": "increase"
         }],
        [{"entity": {
            "type": "Agent",
            "name": "Vemurafenib"
            },
         "perturbation": "increase"
         }]
        ],
      "comparison": "increase"
     }
