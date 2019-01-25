Model Analysis and Testing
==========================

Analysis of scientific models is typically a manual process in which specific
simulation scenarios are formulated in code, executed, and the results
evaluated. In EMMAA, models will be semantically annotated with concepts
allowing scientific queries to be automatically formulated and executed.  The
core component of this process will be a *meta-model* for associating the
necessary metadata with specific model elements.

.. image:: ../_static/images/meta_model_concept.png
   :scale: 50 %

EMMAA models automatically assembled via `INDRA <http://indra.bio>`_ will
already have semantic annotations identifying the relevant entities (e.g.,
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

The meta-model will be implemented in JSON-LD and will allow model elements
encoded in different formalisms to be associated with the concepts necessary
for automated analysis in EMMAA. For example, a protein initial condition
parameter from an executable `PySB <http://pysb.org>`_ model could be linked to
the EMMAA concepts for a parameter that is *naturally varying,*
*non-perturbable,* and *experimentally measurable.* The use of JSON-LD (rather
than RDF, for example) will additionally allow these annotation documents to be
human readable and editable.

Model testing
-------------

.. image:: ../_static/images/model_testing_concept.png
   :scale: 80 %
   :align: right

A key benefit of using semantically annotated models is that it allows models
to be automatically validated in a common framework. In addition to
automatically extracting and assembling mechanistic models, EMMAA will run a
set of tests to determine each model's validity and explanatory scope.  Model
constraints for testing will consist of a combination of high-level qualitative
observations and, where available, structured datasets.

The testing methodology will involve multiple modes of simulation and analysis
including both static and dynamic testing. Static testing will be carried out
by the `Model Checker
<https://indra.readthedocs.io/en/latest/modules/explanation/index.html#module-indra.explanation.model_checker>`_
component of INDRA, which identifies causal paths linking a source or perturbed
variable (e.g., IGF1R) with an output or observed variable (e.g., AKT1
phosphorylated on T308).

A mockup showing a simple test report for a Ras signaling pathway model is
shown below, where each "Observation" is expressed in terms of an expectation
of model behavior (e.g., "IGF1R phosphorylates AKT1 on T308") along with a
determination of whether the constraint was satisfied ("Model Result"), the
number of different paths found, and the length of the shortest path.

.. image:: ../_static/images/testing_mockup.png
   :scale: 60 %

In a manner analogous to continuous integration for software, model testing
will be triggered anytime the model or its associated constraints are updated.
This will be implemented by storing the current state of the model in an Amazon
S3 bucket and associating the bucket with a `Cloudwatch Event
<https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/Create-CloudWatch-Events-Rule.html>`_.
The Cloudwatch Event will trigger the execution of a serverless Amazon Lambda
function responsible for initiating the model testing procedure.

Pre-registered queries and notifications
----------------------------------------

Each EMMAA model will also come with a set of pre-registered queries from
users. The queries will be in a machine-readable representation that utilizes
the meta-model semantics developed for automated model analysis. EMMAA will
initially support the following types of queries (here we show examples in
natural language but we initially imagine these queries to be submitted in a
formal, templated language):

- Structural properties with constraints: e.g., "What drugs bind PIK3CA but not
  PIK3CB?"
- Mechanistic path properties with constraints: e.g., "How does treatment with
  PD-325901 lead to EGFR activation?"
- Simple intervention properties: e.g., "What intervention can reduce ERK
  activation by EGF?"
- Comparative intervention properties: e.g., "How is the effect of targeting
  MEK different from targeting PI3K on the activation of ERK by EGF?"

.. image:: ../_static/images/user_queries_concept.png
   :scale: 60 %
   :align: right

Each such property maps onto a specific model analysis task that can be run on
an EMMAA model, for instance, causal path finding with semantic constraints, or
dynamical simulations under differential initial conditions.

Further, the result of analysis for each property on a given version of the
model will be saved. This will then allow comparing any changes to the result
of analysis with previous states of the model. If a meaningful change occurs, a
notification will be generated to the user who registered the query.


