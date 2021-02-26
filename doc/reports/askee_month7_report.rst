ASKE-E Month 7 Milestone Report
===============================

Demonstrations at the stakeholder meeting
-----------------------------------------

Natural language dialogue interaction with EMMAA models
-------------------------------------------------------

Automatically generated text annotations in context
---------------------------------------------------

Developing the EMMAA REST API for flexible integration
------------------------------------------------------
We continued working on extending EMMAA REST API for the integration with other
teams. One of the key goals was to allow dynamic retrieval of EMMAA models and 
tests metadata. To enable that we implemented four new endpoints in EMMAA REST 
API that support the retrieval of the following data:
- A list of all available EMMAA models;
- Model metadata (short name, human readable name, description, links to NDEx
browsing interface and to model's Twitter account) for a given model;
- A list of test corpora a given model is tested against;
- Test corpus metadata (name and description) for a given test corpus.

Another extension of EMMAA API we implemented is the support for running
queries programmatically. Previously it was only possible to submit the queries
through a form on the Query page of EMMAA dashboard and browse the displayed 
results. The new approach allows our collaborators send programmatic requests 
to the API and receive the results in JSON format. Similarly to the interactive 
interface on the dashboard, the programmatic endpoint supports three types of 
queries: static (find a path between two entities), open search (find upstream 
regulators or downstream targets of an entity), and dynamic (estimate dynamical 
model properties by simulating the model) queries.