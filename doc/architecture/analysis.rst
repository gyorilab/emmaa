Model Analysis and Testing
==========================

.. image:: ../_static/images/model_testing_concept.png
   :scale: 80 %
   :align: right

A key benefit of using semantically annotated models is that it allows models
to be automatically validated in a common framework. In addition to
automatically extracting and assembling mechanistic models, EMMAA runs a
set of tests to determine each model's validity and explanatory scope.
We have implemented an approach to model testing that automates
(1) the collection of test conditions from a pre-existing observational
knowledge base,
(2) deciding which test condition is applicable to which model,
(3) executing the applicable tests on each model, and
(4) reporting the summary results of the tests on each model.



Model test cycle deployed on AWS
--------------------------------

Whenever there is a change to a model, a pipeline on Amazon Web Services (AWS)
is triggered to run a set of applicable model tests. When a model is updated
(i.e., with new findings extracted and assembled from novel research
publictions), a snapshot of it is deposited on the S3 storage service. A
Lambda process monitors changes on S3 and when a change occurs, triggers
a Batch job. The Batch job accesses the Dockerized EMMAA codebase and runs the
automated test suite on the model. The test results are then deposited on
S3. Finally, the new test results are propagated onto the EMMAA Dashboard
website. This process is summarized in the figure below.

.. image:: ../_static/images/testing_pipeline.png
   :scale: 50 %

Test conditions generated automatically
---------------------------------------

EMMAA implements a novel approach to collecting observations with respect to
which models can be tested. Given a set of INDRA Statements, which can be
obtained either from human-curated databases or literature extractions,
EMMAA selects ones that represent experimental observations (which relate a
perturbation to a potentially indirect downstream readout) from direct
physical interaction-like mechanisms. We treat these observational Statements
as constraints on mechanistic paths in a model. For instance, the observation
"treatment with Vemurafenib leads to decreased phosphorylation of MAPK1", could
be satisfied if the model contained a sequence of mechanisms connecting
Vemurafenib with the phosphorylation state of MAPK1 such that the aggregate
polarity of the path is positive.

As a proof of principle, we created a script which generates such a set of
test conditions from the BEL Small Corpus, a corpus of experimental
observations and molecular mechanisms extracted by human experts from the
scientific literature.


Going forward, the testing methodology will involve multiple modes of
simulation and analysis
including also dynamic testing. 


Static testing will be carried out
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

Software architecture for analysis and testing
----------------------------------------------

Automated tests and user-driven queries are designed to be triggered upon any
changes in the underlying model. This


This will be implemented by storing the current state of the model in an Amazon
S3 bucket and associating the bucket with a `Cloudwatch Event
<https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/Create-CloudWatch-Events-Rule.html>`_.
The Cloudwatch Event will trigger the execution of a serverless Amazon Lambda
function responsible for initiating the model testing procedure.

