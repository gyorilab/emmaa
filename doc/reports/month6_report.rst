ASKE Month 6 Milestone Report
=============================

Making model analysis and model content fully auditable
-------------------------------------------------------

When browsing the results of model tests, it is often of interest to inspect
the specific provenance of each modeled mechanisms that contributed to the
result. EMMAA models are built automatically from primary knowledge
sources (databases and literature), and model components are annotated such
that given the result, we can link back to the original sources.

Links to browse evidence are available in all of the following contexts:

- New statements added to the model
- Most supported statements in the model
- New tests applicable to the model
- Passed/failed tests and the mechanisms constituting paths by which tests
  passed

.. image:: ../_static/images/akt_mtor_linkout.png

.. image:: ../_static/images/akt_mtor_curation.png


Including new information based on relevance
--------------------------------------------

EMMAA models self-update by searching relevant litearture each day and adding
mechanisms described in new publications. However, event publications that
are relevant often contain pieces of information that aren't directly relevant
for the model. We therefore created a relevance filter which can take one
of several policies and determine if a new statement is `relevant` to the
given model or not. The strictest policy is called `prior_all` which only
considers statements in which all participants are prior search terms of
interest for the model as relevant. A less strict policy, `prior_one` requires
that at least one participant of a statement is a prior search term for the
model. Currently, EMMAA models are running with the `prior_one` policy.
