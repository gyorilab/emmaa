ASKE Month 9 Milestone Report
=============================

Generalizing EMMAA: a proof-of-principle model of food insecurity
-----------------------------------------------------------------
Until recently, all models in EMMAA represented molecular mechanisms for a
given disease or pathway. However, the EMMAA approach can be applied to
models in other domains. Conceptually, the EMMAA framework is a good fit for
domains where there is a constant flow of novel causal information between
interacting "agents" or "concepts" appearing in a structured or unstructured
form. To demonstrate the generalizability of EMMAA, we created a model
of causal factors influencing food insecurity.

In principle, setting up a new EMMAA model only requires creating a new
configuration file that specifies a name, and description, as well as a
list of search terms, and any optional arguments used to configure the
model building process. In applying EMMAA to a new domain, we extended the set
of options that can be specified in the configuration file, including the
following:

- The literature catalogue to use to search for new content. Biology models
  use PubMed (specific to biomedicine), whereas other domain models can now
  use ScienceDirect (general purpose) to search for new articles.
- The reading system to use to read new text content. The biology models
  in EMMAA query the INDRA Database each day to search for machine reading
  extractions for new publications. The Database contains outputs for two
  biology-specific reading systems (REACH and Sparser) for new daily
  literature content. Models in other domains can be configured to use the
  Eidos reading system (via its INDRA interface) to extract a general set of
  causal relationships between concepts of interest.
- The assembly steps to perform during model extension. We added more
  granularity to configuration options for the model assembly process, making
  it possible to apply biology-specific INDRA assembly steps (e.g., protein
  sequence mapping) only to models where they are relevant.
- The test corpus to use for validating the model. So far, each biology
  model used the same BEL Large Corpus as a source of test statements to
  validate against. We made it possible to configure what test corpus to
  use for a given model, allowing a custom set of relevant tests to be applied
  to the food insecurity moddel.

To set up the initial, proof-of-principle model of food insecurity, we
first identified a set of core concepts of interest: food security, conflict,
flooding, food production, human migration, drought, and markets. We then
filterest a set of extractions by Eidos on a corpus of 500 documents to
causal influences among these concepts. We also set these core concepts as
search terms in the model's configuration file. Finally, we defined a set
common sense statements as test conditions, for instance, "droughts cause a
decrease in food availability" to check the model against. The model is now
included on the EMMAA dashboard where it can be examined
(http://emmaa.indra.bio/dashboard/food_insecurity).

While this initial food insecurity models is a proof of principle for the
generality of the EMMAA concept and the underlying technologies, there are
several challenging aspects of building a good model for this domain.

1. The identification of relevant sources of information. So far, the
   food insecurity model uses ScienceDirect to search for scientific
   publications. However, it is likely that the bulk of timely new information
   is available in reports (by governments, NGOs, etc.) and news stories.
   In the longer term, this would require implementing ways to query and
   collect text content from such sources.
2. Querying for relevant text content. We found that certain search terms
   (e.g., food insecurity) result in mostly relevant publications, while
   others, wuch as "conflict" or "markets" are too broad and ambiguous, and
   result in many irrelevant publications being picked up. This suggests that
   one has to constrain the domain, in addition to the specific concepts
   used as search terms when finding novel literature content.
3. Reading with corroboration. While biology models in EMMAA rely on
   knowledge assembled from multiple machine reading systems as well as
   structured (often human curated) knowledge bases, the food insecurity model
   currently relies on a single reading system, Eidos. This means that any
   systematic errors specific to the reading system are prone to propagate
   into the assembled model. In the longer term, integrating more reading
   systems or knowledge sources could improve on this.
4. Ontologies. Concepts extracted from text are grounded to an ontology, and
   this is the same ontology that is used to assemble statements. The scope
   and resolution of the ontology can be an important limitation.

Extending model testing and analysis to multiple resolutions
------------------------------------------------------------
