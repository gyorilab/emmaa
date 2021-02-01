ASKE-E Month 6 Milestone Report
===============================

Reading and assembly with context-aware organism prioritization
---------------------------------------------------------------

A key challenge in monitoring the COVID-19 literature and modeling the effect
of new discoveries is that descriptions of mechanisms span multiple organisms.
First, we need to be able to recognize both viral proteins and human (or other
mammalian) proteins in text and find possible database identifiers for them.
Second, we need to deal with substantial ambiguity in protein naming between
viral species.

By default, the Reach reading system's named entity recognition module is
configured to tag only human proteins in text. This month, our team developed
a script which cross-references UniProt protein synonyms with the NCBI
Taxonomy to allow generating customized named entity resources which include
protein synonyms for custom sub-trees of the Taxonomy. We used this script
to generate named entity resources that include all human proteins as well
as protein synonyms for all different viral species. We then compiled a custom
version of Reach including these resources.

Next, we implemented a new feature in INDRA which allows processing Reach
output with context-dependent organism prioritization. For a given paper with
a PubMed ID, we can draw on Medical Subject Headings (MeSH) annotations to find
out about organisms that are being discussed. For instance, papers about
Ebola are (typically) tagged with the MeSH heading D029043
(https://meshb.nlm.nih.gov/record/ui?ui=D029043), and papers about SARS-CoV-2
with MeSH heading D000086402 
(https://meshb.nlm.nih.gov/record/ui?ui=D000086402). Once we have a
pre-defined or paper-specific list of relevant organisms, we can process Reach
output with this order in place to choose the highest priority UniProt entry
for each ambiguous entry having been matched.

While our focus here is on coronaviruses (and in particular on SARS-CoV-2),
these new capabilities can be applied to studying other types of existing
viruses, or monitoring the literature on future emerging viral outbreaks.
We have tested the above grounding approach locally but haven't yet
re-processed the entire body of literature (~100k papers) underlying the
EMMAA COVID-19 model. We plan to do this in the next reporting period.

Preparing for the stakeholder meeting
-------------------------------------

The EMMAA COVID-19 model is considerably large since it is configured to
monitor all of the COVID-19 literature without any further restrictions on
model scope. Consequently, for more focused (e.g., pathway-specific) studies,
it makes sense to start with subsets of this overall knowledge, and
demonstrating this
type of more focused model-driven analysis is one of the goals at the upcoming
stakeholder meeting. To prepare for this, we defined six distinct ways in which our models and
REST services can be used to obtain subsets of knowledge on COVID-19
mechanisms, and to extend them using expert knowledge.

First, the EMMAA
COVID-19 model can be queried in at least two ways: using a paper-oriented or
an entity-oriented approach. In the paper-oriented case, one searches for
elements ot the EMMAA COVID-19 model that have support from one or more
specific publications. In the entity-oriented case, one defines a list
of entities of interest, and queries for all model statements that involve
one or more of those entities. The advantage of the paper-oriented approach
is that one does not need to curate a specific entity list up front, but due
to potential recall issues with automated reading, there is no guarantee that
a mechanism of interest will have been extracted from any specific paper.
In contrast, the entity-oriented approach provides more reliable coverage for
the given set of entities while potentially, inadvertently ignoring other
relevant mechanisms.

Second, the general INDRA DB can be used to query for information. The REST API
supports both entity-oriented and paper-oriented queries here as well. The
main difference compared to querying the EMMAA model is that the INDRA DB
results are unfiltered (they can statements that have been marked as incorrect,
 ungrounded entities, statements out of scope, etc.) and may require
 post-processing to get good quality results for a focused modeling study.

Finally, we provide features for experts to build models from scratch or
extend automatically initialized models. For instance, the INDRA API provides an
endpoint to run a machine-reading system on a given span of text (e.g.,
one describing mechanisms for a given pathway in simple English sentences)
and process these into INDRA Statements.

We provided pointers to the Uncharted team for invoking all of these service
endpoints.
