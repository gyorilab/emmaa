ASKE-E Month 9 Milestone Report
===============================

Integrating the COVID-19 Disease Map community model
----------------------------------------------------

Notifications about general model updates
-----------------------------------------

Figures and tables from xDD as non-textual evidence for model statements
------------------------------------------------------------------------

Integration with the Uncharted UI
---------------------------------

We continued working on the integration of EMMAA with the Uncharted UI and
made progress on several fronts. Model exploration in the UI is divided into
two parts, a large-scale network overview, and a more focused drill-down view.

For the network overview, our concept was to use the INDRA ontology - which is
assembled from third-party ontologies in a standardized form - to
hierarchically organize nodes in the network (each node represents a biological
entity or concept) into clusters. This visualization is most effective and
clear if the hierarchical structure of the ontology is fully defined, i.e.,
every entity is organized into an appropriate cluster, and the hierarchy is
organized into an appropriate number of levels. Motivated by this, we spent
considerable effort on improving the INDRA ontology's inherent structure, as
well as creating a custom export script which makes further changes to the
ontology graph specifically to improve the visual layout in the UI.

We also added multiple new features to the EMMAA REST API to support UI
integration. For example, we added an endpoint to load all curations
for a given model, categorizing curated statement into correct, incorrect and
partial labels. Another important feature is providing general information
about entities in each model, including a description, and links to outside
resources describing the entity. To this end, we implemented a new service
called Biolookup (which will be separately deployed) that provides such
information for terms across a large number of ontologies in a standardized
form. We then added an endpoint in the EMMAA REST API which uses Biolookup
to get general entity information and can also add model-specific entity
information to the response.

Our teams have also been involved in many ongoing discussions. These included
deciding on use cases, visual styles, and all aspects of the interpretation of
EMMAA models in order to present them to users in an appropriate way.

Semantic separation of model sources for analysis and reporting
---------------------------------------------------------------

When creating a model of a specific disease or pathway, it often makes sense
to add a set of "external" statements to the model to make it applicable to
a specific data set. A typical example is adding a set of drug-target
statements or a set of phenotypic "readout" statements to a model to connect
it to a data set of drug-phenotype effects. These external statements should
ideally not appear in model statistics. For example, for the COVID-19 Disease
Map model, we marked all drug-target and penotype-readout statements as
external since these were not part of the original model.

Another categorization of statements in models is "curated" vs
"text mined". For instance, the COVID-19 model combines statements mined from
the literature with statements coming from curated sources such as CTD or
DrugBank. Given that we use the COVID-19 Disease Map Model to automatically
explain observations that appear in the COVID-19 Model, it makes sense to
restrict these explanations to statements that aren't "curated".

To achieve this, we extended the EmmaaStatement representation to contain
metadata on each statement that then allows the statements to be triaged
during statistics generation and model analysis.

Assembling and analyzing dynamical models
-----------------------------------------

Creating a training corpus for identifying causal precedence in text
--------------------------------------------------------------------

Knowledge/model curation using BEL annotations
----------------------------------------------

Formalizing EMMAA model configuration
-------------------------------------
