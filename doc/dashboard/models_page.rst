EMMAA Models Page
=================

The models page contains detailed information about the selected model in two
tabs: *Model* and *Tests*. At the top of the page the selected model is
shown in a drop-down menu. Another model can also be selected and loaded from
the menu.

Link to sources
---------------

To see further details regarding a mechanism, links to content databases are
generated for all statements where possible.

.. figure:: ../_static/images/linkout.png
  :align: center
  :figwidth: 75 %

  *Link to content database*

Model Tab
---------

The model tab contains model info with the date the model was last updated and
links to the NDEx website where a network view of the model can be examined.
The page also displays properties of the current state of the model, namely,
the distribution of statement types, the top 10 agents in the model, and the
statements with the most support from various knowledge bases. Further, the
page shows how the number of statements in the model has evolved over time,
and which statements were added to the model during the most recent update.

.. figure:: ../_static/images/aml_model_tab.png
  :align: center
  :figwidth: 75 %

  *The top of the model tab*

Tests Tab
---------

The tests tab contains two related plots: one showing the evolution over time
of the percentage of applicable tests that passed, and another showing the
absolute number of tests that were applied to the model and the number of tests
that passed in each of supported model types. For the first few months of the
project, the tests were only run on a PySB model assembled from EMMAA model
statements. Later three additional model types were added, namely, PyBEL
graph, signed directed graph and unsigned directed graph.

.. figure:: ../_static/images/rasmachine_tests_tab_top.png
  :align: center
  :figwidth: 100 %

  *The top of the tests tab showing the percentage of tests passed together
  with applied and passed tests in different model types*

If any new tests were applied in the latest test run of the model
they are shown under *New Applied Tests*. A green check mark is shown for
tests that passed and a red cross is shown for the tests that did not. The
marks can be clicked on and link to a detailed test results page where the
detailed path(s) or a reason for the model not having passed the test will be
shown. To read more about the detailed test results page, see:
:ref:`detailed_tests_page`.

.. figure:: ../_static/images/new_applied_tests.png
  :align: center
  :figwidth: 100 %
  
  *If new tests were applied, they will be shown together with a breakdown of
  a test status per each model type*

New tests that passed for any of the model types are shown under 
*New Passed Tests* along with the top path found. The statements supporting
the path are can be seen by clicking on a path which links out to the detailed
test results page for the test.

.. figure:: ../_static/images/new_passed_tests.png
  :align: center
  :figwidth: 100 %
  
  *If new tests were passed, they will be shown together with a top path*

Further down, all tests applied to the model are shown. Similarly to new
applied tests, this table also contains green and red marks indicating the test
status, linking to detailed test results page.

.. figure:: ../_static/images/all_test_results.png
  :align: center
  :figwidth: 100 %

  *Part of the list showing all applied tests with a status indicator for
  passed/failed*

Load Previous State of Model
----------------------------

To view the state of the selected model together with the test results for a
particualar date, click on any data point for the desired date in any of the
time series shown on either the Model tab or the Tests tab.

.. figure:: ../_static/images/time_machine_selection_cropped.png
  :align: center
  :figwidth: 100 %

  *Clicking on a data point in any time series will link to the state of the
  model and the test results for the associated date.*

Clicking the data point will link back to the same models page with data
loaded for the selected date. The model info section displays the selected
date as well as the date for the most recent data. Any time series show data
up to the selected date. Any section showing new updates, such as "New
Passed Tests", shows what was new on the selected date while "All Test
Results" shows the state of the results were in. Clicking on "Go To Latest"
on the top panel will link back to the most recent state of the model.

.. figure:: ../_static/images/previous_date_cropped.png
  :align: center
  :figwidth: 100 %

  *When the state of the model for a previous date is shown, the date is
  diplayed in "Data Displayed". Clicking on "Go To Latest" on the top panel
  will link back to the most recent state of the model*
