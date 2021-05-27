ASKE-E Month 10 Milestone Report
================================


Dynamical model analysis
------------------------

Extended automated assembly for model simulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Supporting network-free simulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Adaptive sample-size dynamical property checking
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Intervention-based dynamical queries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration with the Kappa dynamical modeling and analysis UI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Improved EMMAA query UI and REST API
------------------------------------


Network representation learning for EMMAA models
------------------------------------------------
Sets of INDRA statements such as those associated with each EMMAA model can be assembled into
graph-like data structures of decreasing granularity: directed graphs with typed edges,
directed graphs without typed edges, and ultimately, undirected graphs. Different network
representation learning methods can be used for each data structure to assign dense vectors
to nodes (and edges, if applicable). These are useful for downstream machine learning tasks
(e.g., clustering, classification, regression), link prediction, and entity disambiguation.
Our goal is to use the representations to investigate the similarities between nodes' representations
between the full INDRA database and each EMMAA model to identify context-specific nodes as well
as to make recommendations for including or removing nodes from each EMMAA model.

Building a preliminary NRL pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There are both practical and theoretical considerations for using the highest granular directed
graphs with typed edges (i.e., knowledge graphs). Most of the associated methods, called
knowledge graph embedding models (KGEMs), suffer from issues in scalability. Because most useful
biological networks are larger than the size supported, there is still minimal theoretical insight
into how the methods perform on biological networks, which have very different topology to the
`semantic web` datasets to which they are typically applied and evaluated.

Instead, we built a reproducible pipeline for assembling the full INDRA database and each EMMAA model
into directed graphs without typed edges at varying belief levels for application of the `node2vec`
random walk embedding model to generate 64-dimensional vectors in Euclidean space for each node.

Later, we will automate this pipeline to run automatically upon each update to the full INDRA
Database and each EMMAA model such that the latest information can be incorporated. Further, the
results could be included in EMMAA API endpoint that returns model-specific metadata for each node.

Comparing EMMAA models with background knowledge
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
We first investigated where nodes from each EMMAA model appear in the embedding space generated from the full INDRA
database with a belief greater than 60%. We used principal component analysis to project into 2-dimensional space
for visualization. Because of the formulation of the `node2vec` method, each features' contributions to the overall
variance are more homogenous than typical feature sets. The first two principle components only explained ~35% of
the variance. Background nodes are shown with low opacity in blue while EMMAA nodes are shown with high opacity in
orange.

.. image:: ../_static/images/nrl_comparison.png
   :align: center

Interestingly, there are some regions that are not covered by any EMMAA model. While this could be because of a
bias in the contexts covered by current EMMAA models, it might also lead to insight in underrepresented biology.

Identification of context-specific nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Next, we wanted to identify nodes with the most similar and most dissimilar topologies in the INDRA database
and a given EMMAA model. We hypothesize that the most similar nodes represent the most generic biology and
the most dissimilar nodes represent context-specific biology. We investigated the overlap between the k-nearest
neighbors in embedding space for each node in the INDRA Database with the k-nearest neighbors in the embedding
space for each EMMAA model. To account for the size differences in the INDRA database and much smaller EMMAA
models, we used a fractional k=0.05 and the set overlap coefficient, which is more appropriate for sets of different
sizes. We performed the same task on the embeddings generated based on several belief cutoffs.

The following chart shows that when the belief cutoff is increased, the shape of the overlap coefficient rank
distribution typically shifts towards higher overlap coefficients. Darker lines correspond to higher belief.
Notably, this pattern does not hold for the literature derived models (e.g., Pain Model). The RAS Model results
should also be disregarded since the statements there should have an axiomatic belief of 1.0, but are tagged via
TRIPS so have a lower belief.

.. image:: ../_static/images/nrl_belief_plot.png
   :align: center

The nodes in the long tail of these distributions hold the most potential for novelty but also the most liability
for irrelevance. Our next step is to build a minimal browser for looking into these nodes as having a human in the
loop for the investigation of these nodes at the boundaries of EMMAA models could be useful.

Towards an automated recommendation engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Our ongoing work towards an automated recommendation looks at the neighbors of nodes in the EMMAA models within
the embedding space from the full INDRA Database to identify potential additions. We are investigate several clustering
algorithms and their classification counterparts as potential methods for scoring nodes for inclusion. Similarly, we
are investigating anomaly detection methods at can be used in reverse towards the same goal.

Later, we will return to the k-nearest neighbors analysis to identify nodes that could potentially be removed from
a given EMMAA model.

Improvements to :mod:`pykeen`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
While `node2vec` performs well on biological networks due to the symmetry in the model formulation and the important
property of local community structure common to biological networks, we would still like to use more powerful methods
for network representation learning. We are making improvements to the :mod:`pykeen` package for knowledge graph
embeddings in order to make it more scalable and applicable for the directed graph with typed edges assembly of
INDRA statements. So far, we have made several improvements to its memory management on large graphs and begun work
integrating the :mod:`accelerate` for scaling across multiple GPUs.

Integration with the Uncharted UI
---------------------------------


