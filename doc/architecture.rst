EMMAA Initial Architecture and Approach
=======================================

Cancer types of interest
------------------------
We start with six cancer types that are specifically relevant due to a
combination of frequency of occurrence, and lack of treatments.
The cancer types we have initially chosen are as follows. In parentheses,
we give the "code" of each cancer type which corresponds to the subfolder in
emmaa/models in which the model files for the given cancer type are located.
- Acute Myeloid Leukemia (aml)
- Breast Carcinoma (brca)
- Lung Adenocarcinoma (luad)
- Pancreatic Adenocarcinoma (paad)
- Prostate Adenocarcinoma (prad)
- Skin Cutaneous Melanoma (skcm)

Model availability
------------------
The models can currently be browsed through the Network Data Exchange (NDEx)
portal. The EMMAA group on NDEx, listing each model is available here:
http://ndexbio.org/#/group/be7cd689-f6a1-11e8-aaa6-0ac135e8bacf


Defining model scope
--------------------
Each model is initiated with a set of prior entities and mechanisms (that take
entities as arguments). Search terms to extend each model are derived from the
set of entities.

Deriving relevant terms for a given type of cancer
--------------------------------------------------
Our goal is to identify a set of relevant entities (proteins/genes, families,
complexes, small molecules, biological processes and phenotypes) that can be
used to find information relevant to a given model.

This requires three components:
- A method to find entities that are specifically relevant to the given cancer
type
- A background knowledge network of interactions between entities
- A method to identify relevant links and entities on the background knowledge
network

These methods are implemented in the `TcgaCancerPrior` class of the
`emma.priors.cancer_priors` module.

Finding disease genes
~~~~~~~~~~~~~~~~~~~~~
To identify genes that are relevant for a given type of cancer, we turn to
The Cancer Genome Atlas (TCGA), a cancer patient genomics data set available
via the cBio Portal (www.cbioportal.org).

We implemented a client to the cBio Portal which is documented at
https://indra.readthedocs.io/en/latest/modules/databases/index.html#module-indra.databases.cbio_client

Through this client, we first curate a list of patient studies for the given
type of cancer. These patient studies are tabulated in
emmaa/resources/cancer_studies.json.

Next, we query each study with a list of genes (the entire human genome, in
batches) to obtain which patient has mutations in which gene. From this,
we calculate statistics of mutations per gene across the patient population.

Finding relevant entities in a knowledge network
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Finding relevant entities requires a prior network that can be supplied as a
parameter to `TcgaCancerPrior`. We use a network derived from processing and
assembling the content of the
`PathwayCommons <http://www.pathwaycommons.org)/>`_,
`SIGNOR <https://signor.uniroma2.it/>`_,
and `BEL Large Corpus <https://github.com/OpenBEL/openbel-framework-resources/blob/latest/knowledge/large_corpus.xbel.gz>`
databases, as well as machine reading _all_ biomedical literature
(roughly 32% full text, 68% abstracts) with two machine reading systems:
`REACH <http://github.com/clulab/reach>`_, and
`Sparser <http://github.com/ddmcdonald/sparser>`_. This network has
2.5 million unique mechanisms (each corresponding to an edge).

Starting from the mutated genes described in the previous section, we use
a heat diffusion algorithm to find other relevant nodes in the knowledge network.
We first normalize the mutation counts by the length of each protein
(since larger proteins are statistically more likely to have random mutations
which can lack functional significance). We then apply the normalized mutation
count as a "heat" on the node in the network corresponding to the gene.
When calculating the diffusion of heat from nodes, we take into account the
amount of evidence for each edge in the network. The number of independent
evidences for the edge (i.e. the number of database entries or extractions
from various sentences in publications by reading systems) and use a logistic
function with midpoint set to 20 by default (parameterizable) to set a weight
on the edge.


Creating a prior network
------------------------


Updating the network
--------------------

Machine-reading
---------------

Automated assembly
------------------

Model testing
-------------

Model analysis
--------------

Pre-registered queries
----------------------

Notification system
-------------------
