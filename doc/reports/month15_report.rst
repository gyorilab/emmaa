ASKE Month 15 Milestone Report
==============================

EMMAA Knowledge assemblies as alternative test corpora
------------------------------------------------------

During this reporting period we have made two significant updates to our
approach to static analysis of models against observations. First, we have
implemented a prototype capability to generalize EMMMAA knowledge assemblies
for use as either models or as tests. Second, we have implemented the
capability to test a single model against multiple corpora which involved
changes to both the back-end test execution as well as the user interface for
displaying test results.

In EMMAA, daily machine reading is used to update a set of causal relations
relevant to a specific domain, such as a disease, signaling pathway, or
phenomenon (e.g., food insecurity) model. Up until this point, these (possibly
noisy) knowledge assemblies have been used to build causal models that are
checked against a manually-curated observations. We have now also implemented
the converse procedure, whereby the knowledge assemblies are treated as sets of
*observations*, used to check manually curated models.

A prerequisite for this approach is the ability to run a single model
against alternative test suites, which required significant refactoring of
our back-end procedures for triggering testing and results generation,
and new user interfaces to display multiple test results.

As a proof of concept, we converted the EMMAA Statements used to generate the
Ras Machine 2.0 (`rasmachine`) and Melanoma (`skcm`) models into sets of EMMAA
Tests, and checked the manually-curated Ras Model (`rasmodel`) against
each set independently.




Models as te


Time machine
------------

Lorem ipsum

Dynamical model simulation and testing
--------------------------------------

Lorem ipsum

User notifications of newly-discovered query results
----------------------------------------------------

Lorem ipsum
