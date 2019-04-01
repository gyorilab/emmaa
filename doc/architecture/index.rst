.. _emmaa_architecture:

EMMAA Architecture and Approach
===============================

The Ecosystem of Machine-maintained Models with Automated Analysis is
available at http://github.com/indralab/emmaa, with the EMMAA Model Dashboard
at http://emmaa.indra.bio.

The main idea behind EMMAA is to create a set of computational models that are
kept up-to-date using automated machine reading, knowledge-assembly, and model
generation, integrating new discoveries immediately as they become available.

As a key component of the approach, models are automatically tested
against experimental observations (also automatically gathered and associated
with models). Models are also available for automated analysis in which
relevant queries that fall within the scope of each model can be automatically
mapped to structural and dynamical analysis procedures on the model. Currently,
the Dashboard supports running and registering queries with respect to one or
more existing models. In the near future, EMMAA will automatically recognize
and report changes to each model that result in meaningful changes to analysis
results.

.. image:: ../_static/images/emmaa_overview.png
   :scale: 90 %
   :align: center

.. toctree::
   :maxdepth: 4

   assembly
   metamodel
   analysis
   maql
