Meta-Model
----------

Analysis of scientific models is typically a manual process in which specific
simulation scenarios are formulated in code, executed, and the results
evaluated. In EMMAA, models will be semantically annotated with concepts
allowing scientific queries to be automatically formulated and executed.  The
core component of this process will be a *meta-model* for associating the
necessary metadata with specific model elements.

.. image:: ../_static/images/meta_model_concept.png
   :scale: 50 %

EMMAA models automatically assembled via `INDRA <http://indra.bio>`_
have semantic annotations identifying the relevant entities (e.g.,
specific genes or biological processes) and relations (e.g., post-translational
modifications). As shown in the figure above, the EMMAA meta-model will allow
the annotation of:

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

Implementation
~~~~~~~~~~~~~~

The meta-model will be implemented as a formal specification that can be
implemented in different ways depending on the details of the model
implementation; in this way it will resemble the `MIRIAM
<https://co.mbine.org/standards/miriam>`_ (Minimimal Information Required In
the Annotation of Models) standard, but with specific extensions aimed at
automating high-level scientific queries.

In particular, the initial specification for model annotation in EMMAA
will include the following requirements:

- Model processes (e.g., reactions in an ODE model,
  edges in a network model) must be linked to a piece of knowledge including
  provenance and evidence. In our initial implementation, this will be
  accomplished using the `has_indra_stmt` relation which will link back to
  an underlying INDRA statement.
- Model entities (e.g., variables in an ODE model, nodes in a network model)
  must be linked to identifiers 

-
  Model entities must be linked to

