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
search terms in the model's configuration file.


Extending model testing and analysis to multiple resolutions
------------------------------------------------------------
