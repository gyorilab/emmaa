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
configuration file that specifies a name, a description, as well as a
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
filtered a set of extractions by Eidos on a corpus of 500 documents to
causal influences among these concepts. We also set these core concepts as
search terms in the model's configuration file. Finally, we defined a set of
common sense statements as test conditions, for instance, "droughts cause a
decrease in food availability" to check the model against. The model is now
included on the EMMAA dashboard where it can be examined
(http://emmaa.indra.bio/dashboard/food_insecurity).

While this initial food insecurity model serves as a proof of principle for the
generality of the EMMAA concept and the underlying technologies, there are
several challenging aspects of building a good model for this domain.

1. The identification of relevant sources of information. So far, the food
   insecurity model uses ScienceDirect to search for scientific publications.
   However, it is likely that a significant amount of timely new information is
   available in reports (by governments, NGOs, etc.) and news stories.  In the
   longer term, this would require implementing ways to query and collect text
   content from such sources.
2. Querying for relevant text content. We found that certain search terms
   (e.g., food insecurity) result in mostly relevant publications, while
   others, wuch as "conflict" or "markets" are too broad and ambiguous, and
   result in many irrelevant publications being picked up. This suggests that
   one has to constrain the domain, in addition to the specific concepts
   used as search terms when finding novel literature content.
3. Machine reading infrastructure. The biology EMMAA models rely on a
   parallelized AWS infrastructure in which multiple instances of machine
   reading systems can process hundreds or thousands of new publications
   each day. In contrast, the food insecurity model currently relies
   on a single reader instance running as a service, and therefore has
   much lower throughput. Before a comparable infrastructure of readers is
   implemented for this domain, we had to limit the number of new publications
   that are processed each day to update the model.
4. Reading with corroboration. While biology models in EMMAA rely on
   knowledge assembled from multiple machine reading systems as well as
   structured (often human curated) knowledge bases, the food insecurity model
   currently relies on a single reading system, Eidos. This means that any
   systematic errors specific to the reading system are prone to propagate
   into the assembled model. In the longer term, integrating more reading
   systems or knowledge sources could improve on this.
5. Indirect relations. As shown by the initial test set for the food
   insecurity model, all test statements are satisfied by a single
   causal influence statement, even ones where one might reasonably
   expect the test to be satisfied via a chain of causal influences, e.g.,
   "droughts cause a decrease in food availability". We believe that this
   is due to the fact that authors routinely report indirect causal
   influences, and the reading/assembly systems currently aren't set up
   to effectively differentiate between direct and indirect effects.

Extending model testing and analysis to multiple resolutions
------------------------------------------------------------

In our Month 6 Milestone Report, we described an initial experiment to
investigate the value of coarse-grained model testing using simple directed
graphs. In this reporting period we have extended this concept further by
developing a generalized framework for model checking using networks
assembled at different levels of granularity and specificity. In particular,
we are expanding the range of models assembled from a set of EMMAA Statements
to include:

* Directed networks
* Signed directed networks
* PyBEL networks (includes nodes with state information)
* PySB models/Kappa influence maps

For each of these model representations, model checking can be formulated as
a process consisting of three steps:

1. Given a (source, target) statement for checking, identify the nodes
   associated with the source and target. Note that a source or target agent in
   the test statement may correspond to multiple nodes in the give network
   representation.
2. Identify causal paths linking one or more source nodes to one or more target
   nodes. If such a path exists, the test statement is satisfied.
3. Collect paths from the network representation and map them back to the
   knowledge-level (EMMAA statements) for reporting.

The second step in this process, pathfinding over the causal network, is common
to all four of the network representations listed above. However, the first and
third steps--identifying mappings between knowledge-level statements and the
nodes and edges in the network--are specific to each network representation.

To support multi-resolution model checking we have restructured the INDRA model
checker to support multiple model types, with the common code refactored out
into a parent class. In addition we have created an assembler that assembles
INDRA Statements into a new network representation with a metadata model that
can capture the full provenance information from the source INDRA Statements.
This network representation, a multi-digraph called the `IndraNet`, will be
used to generate multiple coarse-grained "views" (digraph, signed digraph),
while preserving statement metadata.

In the upcoming reporting period we will complete this refactoring procedure
and extend the EMMAA web application to generate and display test results for
alternative realizations of each individual knowledge model.

Implementing an object model for model analysis queries
-------------------------------------------------------

We have previously specified a Model Analysis Query Language (MAQL) used
to represent various analysis tasks that can be performed on EMMAA
models, in either a user or machine-initiated way (see :ref:`maql`).

In this reporting period, we implemented a Python object model corresponding
to MAQL. The object model provides a structure for all the attributes needed
to represent a query, and methods to serialize and deserialize it
into JSON. This allows linking the web front-end, the query execution engine,
and the back-end query storage database in a principled way through a single
standardized format. In particular, we have implemented the PathProperty
query class (:py:mod:`emmaa.queries.PathProperty`), and plan to extend to
the other three query types specified in MAQL in the coming months.

Detecting changes in analysis results due to model updates
----------------------------------------------------------

One of the fundamental ideas of the EMMAA framework is to be able to detect
meaningful changes to analyses of interest as model updates happen. We have
implemented an initial solution to this in the QueryManager
(:py:mod:`emmaa.answer_queries.QueryManager`)
whereby the previous results of each registered query are compared to the new
result. Any detected changes are reported in the model update logs (currently
not exposed in the user-facing web front-end yet). A limitation of the current
approach is that the result of a registered query is a single "top" mechanistic
path that satisfies the query conditions, rather than all possible paths. This
means that in some cases, when a new path is created by a new piece of
knowledge, it would not be detected as a change in the query results, unless
the "top" path happens to change. We are planning to improve the change
detection method in this direction.

Further, we are working on adding a user registration functionality. Once
user accounts and user-specific registered queries are created, the next step
will be to create a notification system that exposes the detected changes
in analysis results with respect to a query of interest to the user.



