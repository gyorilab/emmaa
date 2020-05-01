ASKE Month 18 Milestone Report
==============================

Expert curation of models on the EMMAA dashboard
------------------------------------------------
Previously, statements constituting each EMMAA model were linked to an
outside website (the INDRA DB) where they could be curated by users as
correct or incorrect. However, this feature was not convenient for at least
two reasons: the curation required moving to an external website, and
the specific scope and state of each individual EMMAA model was not always
correctly reflected on the more generic INDRA DB site.

Therefore, we implemented several new features in EMMAA that allow curating
model statements (and model tests) directly on the dashboard. Some of the
key places that allow curation include

- The list of most supported statements on the Model tab.
- The list of new added statements on the Model tab.
- 


Viewing and ranking all statements in a model
---------------------------------------------
All statements page / ranking by evidence or test paths


iEmail notifications
-------------------
The system of user notifications for registered queries is now in place and
available to any registered user. On the Query page, when a query is
registered, the user is also signed up for email notifications. This means
that each time a relevant new result is available for the query, the user
receives an email informing them what the new result is, and linking them
to the page on which the new result and its effect on model behavior
can be inspected.

A model of Covid-19
-------------------
Before starting the project, we had planned to set up at least one EMMAA
model of a relevant public health-related process. As the Covid-19 crisis
emerged, we set up an EMMAA model
(https://emmaa.indra.bio/dashboard/covid19/?tab=model) to capture the
relevant existing literature (by building on the CORD-19 corpus). The model
also self-updates each day with new literature on Covid-19, which is now
appearing at a pace of ~500 papers a day, and accelerating.

Configurable model assembly pipeline
------------------------------------

