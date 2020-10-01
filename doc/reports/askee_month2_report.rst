ASKE-E Month 2 Milestone Report
===============================

Push science: EMMAA models tweet new discoveries and explanations
-----------------------------------------------------------------

This month, we implemented and deployed Twitter integration for multiple
EMMAA models. We have previously developed a proof of concept for twitter
integration, however, that framework had significant limitations. First,
tweets only described structural updates to a model (i.e., the number of
new statements that were added) and did not report on any functional changes
or non-trivial new insights that were gained from the model update.
Second, the tweets did not point to any landing page where users could
examine the specific changes to the model. In the new Twitter integration
framework, we addressed both of these crucial limitations.

Twitter updates are now generated for three distinct types of events triggered
by the appearance of new discoveries in the literature:
- New (note that "new" here means that a statement is meaningfully distinct
  from any other statement that the model previously contained) statements
  added to a model.
- The model becoming structurally capable to make a set of new explanations
  with respect to a set of tests (e.g., experimental findings). This typically
  happens if a new entity is added to the model that was previously not
  part of it.
- The model explaining a previously unexplained observatrion (in other words,
  passing a previously failing "test"). These notifications are particularly
  important conceptually, since they indicate that the model learned
  something from the newly ingested literature that changed it such that
  it could explain something it previously couldn't.

The image below shows the first tweet from the
[`EMMAA COVID-19 model`](https://twitter.com/covid19_emmaa).

.. image:: ../_static/images/covid19_twitter.png
    :scale: 75%

Crucially, each of the tweets above include a link to a specific landing page
where the new results can be examined and curated (in case there are any
issues).

Overall, this framework constitutes a new paradigm for scientists to monitor
the evolving literature around a given scientific topic. For instance,
scientists who follow the EMMAA COVID-19 model Twitter account get
targeted updates on specific new pieces of knowledge that were just published
which enable new explanations to drug-virus effects.
