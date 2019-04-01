# EMMAA
EMMAA is an Ecosystem of Machine-maintained Models with Automated Analysis.
The primary way users can interact with EMMAA is by using the EMMAA Dashboard
which can be accessed 
[here](http://emmaa.indra.bio).

## Documentation
For a detailed documentation of EMMA, visit http://emmaa.readthedocs.io.
The documentation contains three main sections:
- A conceptual description of the [EMMAA architecture and approach](https://emmaa.readthedocs.io/en/latest/architecture/index.html)
- An [introduction to the EMMAA Dashboard](https://emmaa.readthedocs.io/en/latest/dashboard/index.html)
- A [module-level documentation of all of EMMAA's code base](https://emmaa.readthedocs.io/en/latest/modules/index.html) linked directly to the source code on Github

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
Users primarily interact with EMMAA via the
[Dashboard](http://emmaa.indra.bio), for which no dependencies need to be
installed.

To set up programmatic access to EMMAA's features locally, do the following:
```
git clone https://github.com/indralab/emmaa.git
cd emmaa
pip install git+https://github.com/sorgerlab/indra.git
pip install git+https://github.com/indralab/indra_db.git
pip install -e .
```

A Dockerized version of EMMAA is available at
https://hub.docker.com/r/labsyspharm/emmaa, which can be obtained as
```
docker pull labsyspharm/emmaa
```

## Funding
The development of EMMAA is funded under the DARPA Automating Scientific
Knowledge Extraction (ASKE) program under award HR00111990009.
