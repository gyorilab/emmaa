Model Analysis Query Language
=============================

This is a specification for a machine-readable description format for
the analysis and querying of EMMAA models. The specification extends to
four, increasingly complex query types:
- Structural properties with constraints
- Mechanistic path properties with constraints
- Simple intervention properties
- Comparative intervention properties

Structural properties with constraints
--------------------------------------
Structural properties of models are evaluated directly at the knowledge-level,
in our case at the level of INDRA Statements. Each Statement has a type (Activation,
Dephosphorylation, etc.), refers to one or more entities (Agents) as arguments,
which themselves can have different types are determined by grounding to
an ontology. At an abstract level

Structural property queries can have different "topologies" in terms of the
entities they reference including (i) unary queries referring to a single
Agent alone, (ii) queries referring to a single Agent and its neighborhood,
(iii) binary queries that refer to two Agents.

Structural property queries may also constrain the type of the Statement

Topological constraints
~~~~~~~~~~~~~~~~~~~~~~~

Entity constraints
~~~~~~~~~~~~~~~~~~

Edge constraints
~~~~~~~~~~~~~~~~


