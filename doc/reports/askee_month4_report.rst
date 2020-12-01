ASKE-E Month 4 Milestone Report
===============================

EMMAA Neurofibromatosis Models and NF Hackathon Prize
-----------------------------------------------------

During this reporting period we won one of the top prizes in the "Hack for NF",
a six-week event sponsored by the Children's Tumor Foundation to develop novel
software relevant to neurofibromatosis (NF), a set of cancer syndromes
that affect children.

Our submission consisted of two causal models of NF deployed in EMMAA.
The first model was built directly from text mining the 18,000 PubMed articles
about NF; it contains approximately 9,000 statements about the functions and
interactions of NF1, NF2, and other entities mentioned in those articles.
Unlike the other cancer-related models in EMMAA, the NF model does not specify
an explicit list of disease-relevant proteins: the scope of the model defined
strictly by neurofibromatosis keyword search terms. This keeps the content of
the model as disease-specific as possible, with the model serving as a
comprehensive representation of what is known about NF.

For the second part of our submission, we substantially expanded our curated
Ras signaling model to include mechanisms relevant to NF1 and NF2 signaling.
The model is transparent even for non-modelers because it is built from about
200 declarative English sentences and assembled by INDRA. In an iterative,
test-driven process, we used the reported causal relationships derived from the
literature-based NF model that were unexplainable by the curated model to both
1) identify errors in the literature derived model and 2) discover necessary
extensions to the curated model.

As an example, the literature-based model contains the laim that NF2 inhibits
PAK1. Using the extended curated model, we can now see that this finding can be
explained by a causal path showing that NF2 competes Angiomotin away from
inhibiting ARHGAP17, thereby causing inhibition of CDC42, which would
otherwise activates PAK1.

As a further demonstration of the scientific value of automated model analysis,
we converted drug screening data from NF1 and NF2 cell lines into EMMAA tests
and checked the literature-derived model against them.  Interestingly, we found
that while the causal paths identified by the models were typically short,
involving paths with a single intermediate node (i.e., drug->protein->cell
proliferation) these explanations were highly context-specific, in some cases
having been identified in the literature as therapeutic vulnerabilities for NF
cell lines.

A diagram showing how see the two types of models (curated and
literature-derived) being used synergistically to explain experimental
results and accumulate actionable knowledge is shown below.

.. image:: ../_static/images/emmaa_nf_model_cycle.png
    :scale: 40%
    :align: center

For this hackathon entry, we won one of the three top prizes. The press
release from the Children's Tumor Foundation can be found
`here, <https://www.ctf.org/news/hack-for-nf-2020-winning-projects>`_
and a video presentation describing our project can be found
`here. <https://www.youtube.com/watch?v=WI-NnFEXY_Y>`_
