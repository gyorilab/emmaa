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
