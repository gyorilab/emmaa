.. _dashboard_query:

EMMAA Model Queries
===================
The Queries page can be accessed by clicking the "Queries" link at the top
of the Dashboard website. The page contains the forms to submit queries and
results of queries in two tabs *Static* and *Dynamic* corresponding to two
currently supported query types.

Static Queries
--------------

This tab allows to submit queries and view the results for static queries that
involve finding mechanistic paths to explain causal relation. Queries are run
against four model types: PySB, PyBEL, signed graph, and unsigned graph.

Submitting a Query
~~~~~~~~~~~~~~~~~~

The model queries page can answer direct queries about one or more models.
A static query consists of a statement type, a subject, and an object.
Together with the query, at least one model needs to be selected for the query
submission to be valid.

.. figure:: ../_static/images/query_filled.png
  :align: center
  :figwidth: 100 %

  *The query ready to be submitted that asks if BRAF activates ERK in the AML
  and BRCA cancer models.*


If the query is badly formatted or missing information, an error will be
shown stating the type of error.

Viewing the results
~~~~~~~~~~~~~~~~~~~

The query will be received by the query service and return a response which is
displayed in the Results table below. Similarly to the results of tests on the
model page, query results are presented as a grid of green, red and grey marks.
A green check mark is shown for queries that passed and a red cross is shown
for the queries that did not. Grey cirlce will be shown for queries not
applicable for selected model. The marks can be clicked on and link to a
detailed query results page where the detailed path(s) or a reason for the
model not having passed the test will be shown.

.. figure:: ../_static/images/path_query_result.png
  :align: center
  :figwidth: 100 %

  *The above query resolved, showing the result per model and model type.
  Detailed results can be viewed by clicking on a green/red mark.*


.. _dashboard_dyn_query:

Dynamical Queries
-----------------

This tab allows to submit and view the results for queries about dynamical
model properties. To answer these queries simulations are run on a
PySB-assembled EMMAA model.

Submitting a Query
~~~~~~~~~~~~~~~~~~

Dynamical query requires the user to specify the model, the entity to run
simulations for, a temporal pattern and, for some patterns, whether the entity
amount should be high or low. An observable entity can be described using
natural language, e.g. "phosphorylated MAP2K1".

.. figure:: ../_static/images/dynamic_query.png
  :align: center
  :figwidth: 100 %

  *The query ready to be submitted that asks whether phosphorylated MAP2K1 is
  eventually high in the MARM model.*

Viewing the results
~~~~~~~~~~~~~~~~~~~

Results of the dynamical queries include a green/red mark showing whether the
required condition was satisfied in more than a half of simulations and a plot
of the observable's time cours during the simulation.

.. figure:: ../_static/images/dynamic_result.png
  :align: center
  :figwidth: 100 %

  *The above query resolved, showing the result per model.*

Waiting for results
-------------------

For either of the query types the page displays "Waiting for server response"
and a loader bar while the query is being executed. The typical response time
can be up to a minute so please be patient when posting queries.

.. figure:: ../_static/images/waiting_for_response.png
  :align: center
  :figwidth: 100 %

  *While the query resolves, a small animation is shown.*

Logging In and Registering a User
---------------------------------

A user can log in by clicking the "Login" button to the right on the
navigation bar. When clicking the login button, an overlay shows up asking
for credentials. A user can also create an account by clicking "Register" if
they don't already have an account.

.. rst-class:: center

   |p1| |p2|

.. |p1| image:: ../_static/images/login_window.png
   :width: 30 %

.. |p2| image:: ../_static/images/registration_window.png
   :width: 30 %

*The login and registration tabs of the login overlay.*

Subscribing to a Query
----------------------

When logged in, a user can register a query for subscription. To register a
subscription to a query, the tick box for "Subscribe To Query" has to be
ticked when the query is submitted. Both static and dynamic queries can be
subscribed to. After submission, the query is associated with the logged in
user. When returning to the page, the subscribed queries will be loaded
together with their latest results.

.. figure:: ../_static/images/subscribed_queries.png
  :align: center
  :figwidth: 100 %

  *The table for subscribed queries, here for the query Activation(FLT3, KRAS)
  of the AML cancer model.*
