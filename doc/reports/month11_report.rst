ASKE Month 9 Milestone Report
=============================

Deployment of multiple-resolution model testing and analysis
------------------------------------------------------------


User-specific query registration and subscription
-------------------------------------------------

We implemented a user registration and login feature in the EMMAA dashboard
which allows registering and subscribing to user-specific queries.
After registering an account and logging in, users can now subscribe to
a query of their interest on the EMMAA Dashboard's Queries page
(https://emmaa.indra.bio/query). Queries submitted by users are stored
in EMMAA's database, and are executed daily with the latest version
of the corresponding models. The results of the new analysis are then
displayed for the user who subscribed to the query on the query page.
This allows users to come back to the EMMAA website daily, and observe how
updates to models result in new analysis results. Later, we are planning
to report any relevant change to the analysis results directly to the user
by sending a notification via email or Slack.

This capability is one important step towards achieving "push science"
in which users are notified about relevant new discoveries if
the inclusion of these discoveries result in meaningful changes in
the context of prior knowledge (i.e., a model) with respect to a
scientific question.
