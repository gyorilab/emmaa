ASKE-E Month 12 Milestone Report
================================

Current state of EMMAA
----------------------

Applying EMMAA model to COVID-19 therapeutics
---------------------------------------------

Progress on inter-sentence causal connective extraction from text
-----------------------------------------------------------------

Integrating belief information in the UI
----------------------------------------

We recently added a new tab on model dashboard to display belief statistics and
browse statements based on their belief scores.

The following plot shows the distribution of belief scores in the COVID-19
EMMAA model. Having it visualized is useful for understanding the effect of
using different belief scorers described in the previous report and of applying
belief filters in the model assembly.

.. figure:: ../_static/images/belief_distr.png
   :align: center

   *Belief scores distribution in RasMachine EMMAA model.*


The next section in the belief tab shows the slider displaying the range of
belief scores in a given model. A user can select a belief range and load the
statements with the belief scores in that range. This gives a new way to
prioritize the statements for the curation.


.. figure:: ../_static/images/belief_range.png
   :align: center

   *Belief scores range slider.*

It is also possible to filter the statements to a given belief score range
from the all statements page.


.. figure:: ../_static/images/belief_filter.png
   :align: center

   *EMMAA model statements filtered to a given belief range.*


Extending ontology to epidemiological use case
----------------------------------------------

Automated modeling review paper
-------------------------------

STonKGs paper
-------------

PyKEEN updates
--------------