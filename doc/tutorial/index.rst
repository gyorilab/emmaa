Walkthrough tutorial
====================

This tutorial demonstrates the use of EMMAA through a scientifically
interesting example related to COVID-19, involving the drug `sitagliptin`.

**Note**: This tutorial uses webm videos. Not all versions of Safari support
webm. We recommend using Chrome or Firefox to play the videos in this
tutorial.

1. Visit the EMMAA Dashboard
----------------------------

**Background**: The EMMAA dashboard is at https://emmaa.indra.bio. The landing page
shows all of the self-updating models available in EMMAA including the COVID-19
model (top right). The landing page also links to Help and Demo videos, and
documentation on the EMMAA REST API for programmatic access.

**Action**: Open your browser and go to emmaa.indra.bio. Then find the Covid-19
model and click on the `Details` button to explore the model.

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_start.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>
    <p>&nbsp;</p>

2. (Optional) Register and log in
---------------------------------

**Background**: The EMMAA dashboard is publicly accessible, however, for
certain features, namely, statement curation, and query registration (more
details later), registering a user account and logging in is necessary.

**Action (Optional)**: Click the blue Login button on the top right and the
Register tab to register first, then enter your details on the Login tab to log
in.

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_login.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>
    <p>&nbsp;</p>

3. Explore the COVID-19 Model page
----------------------------------

**Background**: Having clicked on the Details button for the COVID-19 model, we
arrive on its model exploration page. Here we can see when the model was last
updated, and see a summary of its current status. We can look at the statements
with the most support

**Action**: Scroll through the page and examine each section, hover over the
various plots to see more details. For instance, hover over the plot
in the "Number of Statements over Time" section to see how many statements
were in the model on a given date. Below, take a look at the list of newly
added statements, typically updated each day. In the "Most Supported
Statements" section, find the statement "Sitagliptin inhibits DPP4" and click
on it.

**Science**: It is intriguing that one of the statements with the most
evidence supporting it in the context of the COVID-19 EMMAA model is
about *sitagliptin*, an anti-diabetic medication. Going forward, in this
tutorial, we will explore it as a possible therapeutic.

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_model_page.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>
    <p>&nbsp;</p>
    

4. Examine and curate statement evidences
-----------------------------------------

**Background**: When you click on a statement such as "Sitagliptin inhibits
DPP4", a new page opens up where the underlying evidence supportig the
statement can be examined.

-   In the **header**, both relevant entities, "Sitagliptin"
    and "DPP4" are linked to outside databases (ChEBI and HGNC, respectively) where
    more information about them is available. Next, the green badge with the pencil
    means that there are two user curations for this statement indicating that it
    is correct, i.e., that some of the evidence sentences correctly imply the
    statement. The orange badge on the right shows the belief score of the
    statement, in this case 1, meaning that EMMAA's measure of confidence for this
    statement being correct is high. The gray badge showing 10/318 indicates that
    there are a total of 318 evidences supporting this statement with 10 visible,
    by clicking on the badge, all the evidences can be loaded.  Finally, the purple
    JSON badge allows downloading the statement and its evidences in a
    machine-readable form for downstream processing.

-   In each **evidence row** below the header, a pencil allows curating the statement
    either as correct or incorrect (if incorrect, choose the error type that best
    matches the issue). Next to it, the source of the evidence is shown, for
    instance `sparser` or `reach`, two examples of text mining systems integrated
    with EMMAA. In the middle, the evidence sentence is show with the entities of
    interest highlighted in the text (note that in the header, the names are
    standardized to e.g., standard gene symbols, whereas in scientific text, as
    seen in the evidence, authors often use synonyms).  On the right, a link out to
    the source publication is given, typically to PubMed (the numbers represent
    PubMed identifiers).

**Action**: Browse the evidences for the "Sitagliptin inhibits DPP4" statement.
(Optional) If you registered and logged in, try clicking one of the pencils
next to an evidence row, and add a curation. Try clicking the 10/318 badge
to load all the evidences, and click on one of the PubMed ID links on the right
to see one of the source publications.

**Science**: Based on the evidence available here, we find that sitagliptin is
discussed in a large number of publications as a drug that inhibits the DPP4
protein.  The evidence sentences and source publications indicate relevance not
only in treating diabetes but also as an anti-inflammatory drug. It could
therefore be specifically relevant for COVID-19 treatment.


.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_statement_drilldown.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>
    <p>&nbsp;</p>
    

5. Bowse all statements in the model
------------------------------------

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_all_stmts.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>
    

6. Examine drug-virus effect explanations
-----------------------------------------

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_tests.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>

7. Drill-down into explanation results
--------------------------------------

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_tests_sitagliptin.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>

8. Browse the model from the perspective of papers
--------------------------------------------------

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_papers.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>

9. Query the model to find source-target paths
----------------------------------------------

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_query_source_target.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>
    

Query result statement view, figures tab

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_query_source_target_figures.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>

10. Query the model to find upstream regulator paths
----------------------------------------------------

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_query_open_search.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>
    

11. Chat with a machine assistant about the COVID-19 model
----------------------------------------------------------

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_chat.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>

12. Follow the COVID-19 EMMAA model on Twitter
----------------------------------------------

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_twitter.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>
