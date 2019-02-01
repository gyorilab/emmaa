Meta-Model
==========

Analysis of scientific models is typically a manual process in which specific
simulation scenarios are formulated in code, executed, and the results
evaluated. In EMMAA, models will be semantically annotated with concepts
allowing scientific queries to be automatically formulated and executed.  The
core component of this process will be a *meta-model* for associating the
necessary metadata with specific model elements.

.. image:: ../_static/images/meta_model_concept.png
   :scale: 50 %

As shown in the figure above, the EMMAA meta-model will allow
the annotation of:

- relevant entities (e.g., specific genes or biological processes)
- relations/processes (e.g., phosphorylation, activation)
- quantities in model-relevant data (e.g., measured values associated with
  specific model parameters)
- features of model parameters and observables relevant to subsequent
  experimental follow-up (e.g.,for example whether a parameter can be
  experimentally altered or whether measurement of a particular observable is
  cost-effective)
- higher-level scientific aspects associated with model variables and outcomes,
  such as the utility associated with particular model states (e.g., decreased
  cell proliferation)

The meta-model allows model elements encoded in different formalisms to be
associated with the concepts necessary for automated analysis in EMMAA. For
example, a protein initial condition parameter from an executable `PySB
<http://pysb.org>`_ model could be linked to the EMMAA concepts for a parameter
that is *naturally varying,* *non-perturbable,* and *experimentally
measurable.* The use of JSON-LD (rather than RDF, for example) will
additionally allow these annotation documents to be human readable and
editable.

Initial specification of annotation guidelines
----------------------------------------------

The meta-model will be implemented as a specification that can be implemented
in different ways depending on the model type; in this way it will resemble the
`MIRIAM <https://co.mbine.org/standards/miriam>`_ (Minimimal Information
Required In the Annotation of Models) standard, but with specific extensions
aimed at automating high-level scientific queries.

In particular, the initial specification for model annotation in EMMAA
will include the following requirements to support basic simulation and
analysis tasks:

1. Model entities (e.g., variables in an ODE model, nodes in a network model)
   must be linked to identifiers in external ontologies.
2. Entity states (e.g., phosphorylated, mutated, active or inactive proteins)
   should be identified semantically variables using an external ontology or
   controlled vocabulary.
3. Model processes (e.g., reactions in an ODE model,
   edges in a network model) must be linked to a piece of knowledge including
   provenance and evidence. In our initial implementation, this will be
   accomplished using the `has_indra_stmt` relation which will link back to
   an underlying INDRA statement.
4. Entities participating in processes should be identified with
   their role (e.g subject or object) for directional analysis.
5. (Optional): if it is not already implicit in the modeling formalism, the
   model process can be annotated with the `sign` of the process on its
   participants (i.e., positive or negative regulation).

"Does X..." queries currently supported for PySB models
-------------------------------------------------------

Implementing the five requirements above supports high-level queries such as:
"Does treatment with drug X cause an increase in the phosphorylation of protein
Y?" Answering this high-level query makes use of model annotations in the
following way:

- Entities in the model representing drug X are identified (#1,
  above).
- Entities in the model representing phosphorylated Y are identified
  (#1 and 2).
- Processes with drug X as the subject are identified, as are processes
  with phosphorylated Y as the object (#4, above).
- The effect of the drug X entities/processes on the phosphorylated protein Y
  entities/processes are determined using a model-specific analytical procedure,
  making use of `sign` information if necessary (#5).
- The analysis results are linked back to the knowledge model via
  `has_indra_stmt` annotations.

We currently have an end-to-end implementation that uses model annotations to
answer these types of queries for a single model type, executable dynamical
models implemented in PySB. Model annotations are generated as part of the
model assembly process; for instance see `the PySB Assembler code here
<https://github.com/sorgerlab/indra/blob/master/indra/assemblers/pysb/assembler.py#L1190>`_
for an example of how the `PySB Annotation class
<https://github.com/pysb/pysb/blob/master/pysb/annotation.py>`_ is used to
associate a entities with their role (subject/object) in a process (#4).

To answer a "does" query like the one specified above, the `ModelChecker
<https://github.com/sorgerlab/indra/blob/c5f15dfe9f30f71cc1b8798e7c9042c4d10bd051/indra/explanation/model_checker.py#L144>`_ makes use of these annotations
to search for a path through the model's influence map with the appropriate
sign.

Annotations required for "what if" queries
------------------------------------------

As opposed to a "does X..." query like the example above, which are used to
determine the connectivity and sign of causal paths in the model at baseline,
a "what if" query indicates a perturbation and involves an open-ended
response. For example, consider the following queries:

- "What happens to protein X if I knock out protein Y?"
- "What happens to protein X if I double the amount of drug Y?"
- "What happens to protein X if I decrease its affinity to drug Y?"

Addressing these queries in general requires designating a model `control
condition` (e.g., a specific initial state or steady state) that is perturbed
by the manipulation of model structure or parameters. This requires the
following model features to be identified by additional annotations:

6. Model parameters governing entity amounts
7. Effect of model parameters on the strength of interaction between entities
   (for example, the forward and reverse rates of a binding interaction both
   affect the affinity of the interaction, but in opposite ways).

Annotations required for open-ended "relevance" queries
-------------------------------------------------------

Finally, we aim to enable the automation of analysis procedures that are not
based on explicit queries but rather aimed at identifying model characteristics
that have scientific relevance and value. An example would be to "notify me of
mechanistic findings therapeutically relevant to pancreatic cancer." This type
of query requires additional annotations on the higher-level biological
processes associated with model entities and their scientific relevance. We aim
to implement the following additional three annotations for this purpose:

8. Biological processes or phenotypes associated with specific model
   entities, and their sign (e.g., phosphorylated MAPK1 is positively
   associated with cell proliferation in pancreatic cancer).
9. A value criterion associated the biological process (e.g., it is
   therapeutically desirable to `increase` cancer cell apoptosis,
   and `decrease` cancer cell proliferation).
10. Entity types that represent actionable perturbations. For example,
    it may be of greater interest to identify a chemical perturbation that
    yields a desirable affect than a genetic perturbation, because (at least
    present) chemical perturbations are more experimentally and therapeutically
    tractable.

These ten annotation types represent the initial set for the EMMAA cancer
models.
