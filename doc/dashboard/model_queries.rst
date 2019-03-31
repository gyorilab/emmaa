EMMAA Model Queries
===================
The Queries page can be accessed by clicking the "Queries" link at the top
of the Dashboard website.

Submitting a Query
------------------

The model queries page can answer direct queries about one or more models.
A query
consists of a statement type, a subject, and an object. Together with the
query, at least one model needs to be selected for the query submission to be
valid. A query can also optionally be submitted for registration. With this
option, when returning to the page, previous queries will be loaded with
their latest result.

.. figure:: ../_static/images/query_filled.png
  :align: center
  :figwidth: 100 %

  *The query ready to be submitted that asks if BRAF activates ERK in the AML
  cancer model.*

If the query is badly formatted or missing information, an error will be
shown stating the type of error.

The query will be received by the query service and return a
response which is displayed in the Results table below. The result for each
model is either a mechanistic path reported in English language which satisfies
the query condition, or an explanation of why the query could not be evaluated
on the model.

The page displays "Waiting for server response" and a loader bar
while the query is being executed. The typical response time can be up to a
minute so please be patient when posting queries. 
