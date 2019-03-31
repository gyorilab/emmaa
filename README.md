# EMMAA
EMMAA is an Ecosystem of Machine-maintained Models with Automated Analysis.
The primary way users can interact with EMMAA is by using the EMMAA Dashboard
which can be accessed 
[here](http://emmaa.indra.bio).

## Documentation
For a detailed documentation of EMMA, visit http://emmaa.readthedocs.io

## Concept
The main idea behind EMMAA is to create a set of computational models that
are kept up-to-date using automated machine reading, knowledge-assembly, and
model generation. Each model starts with a prior network of relevant concepts
connected through a set of known mechanisms. This set of mechanisms is then
extended by reading literature or other sources of information each day,
determining how new information relates to the existing model, and then
updating the model with the new information.

Models are also available for automated analysis in which relevant queries
that fall within the scope of each model can be automatically mapped
to structural and dynamical analysis procedures on the model. This allows
recognizing and reporting changes to the model that result in meaningful
changes to analysis results.

## Applications
The primary application area of EMMAA is the molecular biology of cancer,
however, it can be applied to other domains that the INDRA system and the
reading systems integrated with INDRA can handle.

## Installation
The primary dependency of EMMAA is INDRA which can be installed using pip.
Depending on the application, third-party dependencies of INDRA may need
to be installed and configured separately.

## Funding
The development of EMMAA is funded under the DARPA Automating Scientific
Knowledge Extraction (ASKE) program.
