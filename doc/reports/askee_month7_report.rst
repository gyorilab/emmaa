ASKE-E Month 7 Milestone Report
===============================

Demonstrations at the stakeholder meeting
-----------------------------------------

Natural language dialogue interaction with EMMAA models
-------------------------------------------------------

Automatically generated text annotations in context
---------------------------------------------------
As an extension of the paper centered view of model statements reported last month
we integrated EMMAA with the hypothes.is service that allows annotating webpages.
The figure below illustrates the relevant part of the updated "Paper" tab on the
EMMAA dashboard.

.. image:: ../_static/images/hypothesis_badge.png

For each paper from which statements were extracted, a small hypothesis ("h.") badge is
displayed. Clicking on this badge starts the process of uploading the annotations
for statements extracted from this paper. After all annotations are added, an
external page with this paper opens up in a new tab. In addition, a link to this
page is displayed on the EMMAA website.

.. image:: ../_static/images/annotations_added.png

Viewing the uploaded annotations requires the user to install the hypothes.is
extension in their browser. The figure below shows how annotations can be viewed and
edited on the newly opened page. In this example, a paper on PubMed Central was
automatically annotated. The sentences supporting each of the extracted statements are
highlighted in the paper and the statements can be viewed in the annotations
panel on the right. For instance, this image shows the highlighted sentence
mentioning "FGF1–heparin complex" and the extracted "heparin binds FGF1" INDRA
statement.

.. image:: ../_static/images/annotations_displayed.png

Developing the EMMAA REST API for flexible integration
------------------------------------------------------
We continued working on extending the EMMAA REST API to support integration with other
teams. One of the key goals was to allow dynamic retrieval of EMMAA models and
tests metadata. To enable this, we implemented four new endpoints in the EMMAA REST
API that support the retrieval of the following data:

    - A list of all available EMMAA models;
    - Model metadata (short name, human readable name, description, links to the NDEx
      landing page and to the model's Twitter account) for a given model;
    - A list of test corpora a given model is tested against;
    - Test corpus metadata (name and description) for a given test corpus.

Another important extension of the EMMAA API we implemented is the support for running
queries programmatically. Previously it was only possible to submit queries
through a web form on the Query page of the EMMAA dashboard and then browse the displayed
results. The new approach allows our collaborators to send programmatic requests
to the API and receive the results in JSON format. Similarly to the interactive
interface on the dashboard, the programmatic endpoint supports three types of
queries: static (find directed paths between two entities), open search (find upstream
regulators or downstream targets of an entity), and dynamic (confirm dynamical
model properties by simulating the model) queries.