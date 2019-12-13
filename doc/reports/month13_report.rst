ASKE Month 13 Milestone Report
==============================

Related work for the EMMAA system
---------------------------------

We are not aware of any meta-modeling systems coupling machine-assembled models
to automated analysis, in molecular biology or other fields. To the best of our
knowledge, the EMMAA system is the first of its kind.

Nevertheless, members of the cancer biology community have argued for the
usefulness of such a system - if it existed - for instance, in a perspective
piece by Carvunis & Ideker (2016). Despite the fact that EMMAA is unique as an
integrated system, there does exist a body of pre-existing work related to
individual component technologies of the system.

Mathematical and causal modeling has been widely applied in systems biology,
where a multitude of model types (ordinary and partial differential equations,
Boolean and logical models, probabilistic graphical models, etc.) have been
used to represent the behavior of biochemical mechanisms (Aldridge et al.,
2006). However, such models are difficult and time consuming to build, and
require special mathematical and computational expertise. To address this,
EMMAA draws on novel tools allowing the automated assembly of mathematical
models directly from text (INDRA; Gyori et al., 2017).

There also exists a large body of work in text mining in biomedicine (Ananiadou
et al., 2006), motivated by the fact that around 3,200 new publications appear
every day - too much for any human expert to keep up with. However, the output
of these systems have thus far not been combined (EMMAA currently integrates
and aligns output from 4 different text mining systems: REACH
(Valenzuela-Escárcega et al., 2019), Sparser (McDonald et al., 2016),
TRIPS/DRUM (Allen et. al., 2015) and RLIMS-P (Torii et al., 2015)) and made
available for natural language querying by users. Recently, a graphical user
interface was proposed to explore causal relations extracted by a single
reading system (Barbosa et al., 2019). However, the causal networks built using
this system do not make use of the knowledge assembly procedures built into
EMMAA, including correction of systematic reading errors, and assessment of
redundance, relevance, and believability.

Further, several large human-curated knowledge-bases for molecular mechanisms
have been developed (Cerami et al, 2010, Croft et al., 2013), and can be
queried through their respective websites through standard web forms. Finally,
large repositories of experimental and clinical data are routinely used in
biomedicine (Keenan et al., 2018, Tomczak et al., 2015). However, while such
repositories exist, they grow only through manual curation and are often out of
date.

Finally, while the concept of model testing and validation, either static or
dynamic, is not new, this has (to our knowledge) only been applied to specific
models in isolated modeling studies. There exists no framework for the
systematic evaluation of domain models with respect to relevant tests; nor are
there any previous demonstrations of the use of text mining to automatically
grow a body of observations for use in model evaluation.

References
~~~~~~~~~~

Aldridge, B. B., Burke, J. M., Lauffenburger, D. A., & Sorger, P. K. (2006). Physicochemical modelling of cell signalling pathways. Nature cell biology, 8(11), 1195.

Gyori, B. M., Bachman, J. A., Subramanian, K., Muhlich, J. L., Galescu, L., & Sorger, P. K. (2017). From word models to executable models of signaling networks using automated assembly. Molecular systems biology, 13(11).

Ananiadou, S., & McNaught, J. (2005). Text mining for biology and biomedicine (pp. 1-12). London: Artech House.

Valenzuela-Escárcega, M. A., Babur, Ö., Hahn-Powell, G., Bell, D., Hicks, T., Noriega-Atala, E., ... & Morrison, C. T. (2018). Large-scale automated machine reading discovers new cancer-driving mechanisms. Database, 2018.

McDonald, D., Friedman, S., Paullada, A., Bobrow, R., & Burstein, M. (2016, March). Extending biology models with deep NLP over scientific articles. In Workshops at the Thirtieth AAAI Conference on Artificial Intelligence.

Allen, J., de Beaumont, W., Galescu, L., & Teng, C. M. (2015, July). Complex Event Extraction using DRUM. In Proceedings of BioNLP 15 (pp. 1-11).

Torii, M., Arighi, C. N., Li, G., Wang, Q., Wu, C. H., & Vijay-Shanker, K. (2015). RLIMS-P 2.0: a generalizable rule-based information extraction system for literature mining of protein phosphorylation information. IEEE/ACM Transactions on Computational Biology and Bioinformatics (TCBB), 12(1), 17-29.

Barbosa, G. C., Wong, Z., Hahn-Powell, G., Bell, D., Sharp, R., Valenzuela-Escárcega, M. A., & Surdeanu, M. (2019, June). Enabling Search and Collaborative Assembly of Causal Interactions Extracted from Multilingual and Multi-domain Free Text. In Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics (Demonstrations) (pp. 12-17).

Cerami, E. G., Gross, B. E., Demir, E., Rodchenkov, I., Babur, Ö., Anwar, N., ... & Sander, C. (2010). Pathway Commons, a web resource for biological pathway data. Nucleic acids research, 39, D685-D690.

Croft, D., Mundo, A. F., Haw, R., Milacic, M., Weiser, J., Wu, G., ... & Jassal, B. (2013). The Reactome pathway knowledgebase. Nucleic acids research, 42(D1), D472-D477.

Keenan, A. B., Jenkins, S. L., Jagodnik, K. M., Koplev, S., He, E., Torre, D., ... & Kuleshov, M. V. (2018). The library of integrated network-based cellular signatures NIH program: system-level cataloging of human cells response to perturbations. Cell systems, 6(1), 13-24.

Tomczak, K., Czerwińska, P., & Wiznerowicz, M. (2015). The Cancer Genome Atlas (TCGA): an immeasurable source of knowledge. Contemporary oncology, 19(1A), A68.


