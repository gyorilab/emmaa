ASKE-E Month 1 Milestone Report
===============================

Overall goals and use cases for the Bio Platform
------------------------------------------------

The goal of the Bio Platform is to provide an automated modeling and
model analysis platform (with appropriate interfaces for user-in-the-loop
interaction) around the molecular basis of diseases and their therapies.
The initial disease focus for the platform is COVID-19. In this context,
the use cases we aim to work towards are as follows:

- Explain drug mechanisms based on existing experimental observations

  - Example: through what mechanism does E64-D decrease SARS-CoV-2 replication?

- Propose new drugs that haven't yet been tested

  - Example: Leupeptin should be investigated since through protease
    inhibition, it is expected to decrease SARS-CoV-2 entry.

- Causally/mechanistically explain high-level/clinical associations
  that are unexplained

  - Example: What is the mechanistic basis for men being susceptible to more
    severe COVID-19 compared to women?

- Construct reports on the implication of therapeutics on clinical outcomes,
  optimize course of therapy

  - Example: Find the optimal course of interferon treatment using modeling
    and simulation.

Integration plan for the Bio Platform
-------------------------------------

The following diagram shows the integration architecture for the Bio
Platform:

.. image:: ../_static/images/bio_platform.png

The main components of this integration are as follows. The HMS team's INDRA
system integrates multiple knowledge sources, including the Reach and Eidos
machine-reading systems developed by the UA team. INDRA is also integrated with
UW's xDD system where it is run on a subset of published papers and preprints
to produce statements that INDRA doesn't otherwise have access to.
INDRA produces statements daily that are picked up by EMMAA (each EMMAA model
gets only statements that are specifically relevant to its use case as
controlled by a definition of model scope). Each EMMAA model then assembles
its statements in a use-case-specific way to produce an assembled knowledge
base. This is then the basis of generating multiple executable / analyzable
model types (unsigned graph, signed graph, PyBEL, PySB) and applying these
models to automatically explain a set of observations (note that this process
can also be thought of as "testing" or "validation" of the model).
EMMAA integrates with the MITRE Therapeutics Information Portal by pulling
in observations about drug-virus relationships that it then explains.
The resulting explanations (typically mechanistic paths) will be linked
back to the MITRE portal. The portal will also link to INDRA-assembled
information on specific drugs and their targets.
Finally, EMMAA will integrate with the Uncharted UI both at the level of
the knowledge base that each model constitutes, and the explanations
produced by each model.

Progress during the ASKE-E Hackathon
------------------------------------


Open Search model queries and notifications
-------------------------------------------

