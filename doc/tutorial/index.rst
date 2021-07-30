Walkthrough tutorial
====================

This tutorial demonstrates the use of EMMAA through a scientifically
interesting example related to COVID-19, involving the drug `sitagliptin`.

In each section, the **Background** block provides a description of some part
of the EMMAA dashboard and explains the key concepts behind it. The **Action**
block telss you what specifically to do at each step. Finally, the **Science**
block provides insights and observations gained along the way about our
scientific use case of interest.

Each section also contains a short (less than one minute) video that you can
watch to guide your exploration.

**Note**: This tutorial uses webm videos. Not all versions of Safari support
webm. We recommend using Chrome or Firefox to play the videos in this tutorial.

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

**Background**: EMMAA allows browsing, sorting and filtering all the statements
in the model according to a few different criteria. The default sort order is
by evidence count (see gray badge on the right in each header). See Section 4
for a detailed description of each statement header (and when clicked to
expand) each evidence row underneath. In some of the statement headers, you see
a blue badge with a flag and a number. The number here represents the number of
explanatory paths that this statement is part of when the EMMAA COVID-19 model
is used to automatically explain a set of drug effects on a set of viruses.
Statements that have a high path count are specifically important since they
play a role in analysis results. The "Sorting by evidence" dropdown allows
sorting statements by paths (i.e., the number in the blue badges) or belief
(i.e., the number in the orange badges). The "Filter by statement type"
drowpdown also allows looking at only certain types of statements such as
Activation or Phosphorylation.

**Action**: On the EMMAA COVID-19 model page, next to the "Most Supported
Statements" header, click on the "View All Statements" button. Scroll down the
page to see example statements and click on any that you find interesting to
examine its evidence. Then click on the "Sorting by evidence" dropdown and
select "Sorting by paths", and click "Load Statements".  This gives you a list
of statements based on how often they appear on paths explaining drug effects
on viruses.

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_all_stmts.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>
    

6. Examine drug-virus effect explanations
-----------------------------------------

**Background**: The EMMAA COVID-19 model can be used to explain experimental
observations. This automated analysis feature is crucial to EMMAA and
demonstrates that EMMAA can turn raw knowledge extracted from scientific text
into actionable models. The COVID-19 model is compiled into a signed (e.g.,
statement types like activation or inhibition imply positive and negative
signs, respectively) and unsigned (i.e., statement types are ignored) graph,
and semantically constrained automated path finding is performed to reconstruct
mechanistic paths that connect a perturbation to a readout. Given data
sets of perturbations and readouts, EMMAA performs this analysis daily, with
each model update - and each new piece of knowledge modeled - the results
potentially changing.

This aspect of EMMAA is also called "testing" (hence the "Tests" tab) since the
results of these explanations, i.e, how many observations the model can explain
are also indicative of the scope and quality of the model. On the Tests tab,
one can select a corpus of observations. For the EMMAA COVID-19 model, we
have two such test corpora available, the "Covid19 curated tests" represent
positive hits in cell-based assays for drugs inhibiting SARS-CoV-2 or
another coronavirus, curated by our team from publications. The "Covid19 mitre
tests" corpus is integrated from the MITRE Therapeutics Information Portal
and represents drugs that are known to or studied to affect SARS-CoV-2
or other coronaviruses. The test page shows plots of how many tests
"passed" (i.e., explanations were successfully found) over time as the
model evolved. It also allows looking at the specific explanations found
for each test under the "All Test Results" section by clicking on the green
checkmark next to a test.

**Action**: On the EMMAA COVID-19 model page, click on the "Tests" tab. Then
under Test Corpus Selection, select "Covid19 mitre tests" and click "Load Test
Resutlts". Now hoveer over the two plots showing the percentage of tests passed
and passed and applied tests to see how the model's explanations evolved over
time. Then scroll down to the "All Test Results" section and see the list of
drug-virus effects for which there are automatically constructed explanations.

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_tests.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>

7. Drill-down into explanation results
--------------------------------------

**Background**: To learn more and see if an explanation makes sense
you can click on the statements underlying the explanation and curate
any incorrect statements.

**Action**: Scroll down to find (or use your browser's search) to find
the test row in which "Sitagliptin inhibits SARS-CoV-2" in the "All Test
Results" section. Then click on the green checkmark in the first (signed
graph) column. This brings you to a page where you can see the specific
explanation EMMAA found. Currently (note that explantions can change over time
as the model evolves) the explanation shown here indicates the ACE protein as
an intermediate on sitagliptin's effect on SARS-CoV-2. Click on the statement
"Sitagliptin activates ACE" on the right to see its evidence.

**Science**: Interestingly, ACE appears to be an intermediate mediating
sitagliptin's effect on SARS-CoV-2. Examining the evidence for sitagliptin's
effect on ACE - while the polarity of this extraction happens to be incorrect -
it still draws our attention to an important observation, namely that
both sitagliptin, and another DPP4 inhibitor, linagliptin are both able
to inhibit ACE, a protein not directly responsible for (like ACE2), but
involved in SARS-CoV-2 infection.

.. raw:: html

    <video width="700" controls>
    <source src="../_static/images/emmaa_tutorial_tests_sitagliptin.webm" type="video/webm">
    Your browser does not support the video tag.
    </video>

8. Browse the model from the perspective of papers
--------------------------------------------------

**Background**: The third tab after "Model" and "Tests" we explore here is the
"Papers" tab which allows exploring the COVID-19 model from the perspective
of individual publications.

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
