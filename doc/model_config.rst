.. _config_doc:

Configuring an EMMAA model
==========================

Each EmmaaModel has to be initiated with a config.json file. Config files can
be generated manually or automatically with relevant methods in :ref:`priors`
module (e.g. see :ref:`literature_prior` to start a model with default config
from literature).
This document describes the structure of the config.


First level fields of config.json
---------------------------------

- `name` : str
    A short name of a model.

    - Example: aml

- `search_terms` : list
    A list of jsonified SearchTerms (see `emmaa.priors`) to search the
    literature for.

    - Example:

    .. code-block:: json

        [{"type": "gene",
          "name": "PRKCA",
          "db_refs": {"HGNC": "9393", "UP": "P17252"},
          "search_term": "'PRKCA'"},
         {"type": "drug",
          "name": "SB 239063",
          "db_refs": {"HMS-LINCS": "10036",
                      "PUBCHEM": "5166",
                      "LINCS": "LSM-44951",
                      "CHEBI": "CHEBI:91347"},
          "search_term": "'SB 239063'"}]

- `human_readable_name` : str
    A human readable name of the model that will be displayed on the dashboard.

    - Example: Acute Myeloid Leukemia

- `ndex` : dict, optional
    Configuration for NDEx network formatted as `{"network": <NDEx network ID>}`

    - Example:

    .. code-block:: json

        {"network": "ef58f76d-f6a2-11e8-aaa6-0ac135e8bacf"}

- `description`: str
    Description of a model (will be displayed on EMMAA dashboard).

    - Example: A model of molecular mechanisms governing AML, focusing on
      frequently mutated genes, and the pathways in which they are involved.

- `dev_only` : bool, optional
    Set to True if this model is still in development mode and should not be
    displayed on the main emmaa.indra.bio dashboard. Default: False.

- `twitter` : str, optional
    If the model has Twitter account, this field should provide a key to
    retrieve Twitter secret keys stored on AWS SSM.

    - Example: covid19

- `twitter_link` : str, optional
    URL to model's Twitter account if it exists.

    - Example: https://twitter.com/covid19_emmaa

- `run_daily_update` : bool
    Whether the model should be updated with new literature daily.

- `export_formats` : list[str], optional
    A list of formats the model can be exported to. Accepted values include:
    `indranet`, `pybel`, `sbml`, `kappa`, `kappa_im`, `kappa_cm`, `gromet`,
    `bngl`, `sbgn`, `pysb_flat`, `kappa_ui`. Note that `kappa_ui` option does
    not generate a separate export file but adds a link to Kappa interactive
    UI that uses model's kappa export (generated if `kappa` is in this list).

- `assembly` : dict or list[dict]
    Configuration of model assembly represented as a dictionary where each
    key is a type of assembly (`main` for general purpose assembly steps and
    `dynamic` for additional steps to assemble a simulatable model) and
    values should contain corresponding jsonified steps to pass into the INDRA
    AssemblyPipeline class. Each step should have a `function` key and, if
    appropriate, `args` and `kwargs` keys.
    For more information on AssemblyPipeline, see
    https://indra.readthedocs.io/en/latest/modules/pipeline.html
    For backward compatibility, if a model has only one type of assembly
    (`main`), assembly configuration can be a list of steps instead of a
    dictionary with assembly types.

    - Example:

    .. code-block:: json

        {"main": [
            {"function": "map_grounding",
             "kwargs": {"grounding_map": {
                "Viral replication": {"MESH": "D014779"},
                "viral replication cycle": {"MESH": "D014779"}}}},
            {"function": "run_preassembly",
             "kwargs": {"return_toplevel": false,
                        "belief_scorer": {
                            "function": "load_belief_scorer",
                            "kwargs": {"bucket": "indra-belief",
                                       "key": "1.20.0/default_scorer.pkl"}
                            }
                        }},
            {"function": "filter_by_curation",
             "args": [{"function": "get_curations"},
                      "any",
                      ["correct", "act_vs_amt", "hypothesis"]],
             "kwargs": {"update_belief": true}}
            ],
         "dynamic": [
            {"function": "filter_by_type",
             "args": [{"stmt_type": "Complex"}],
             "kwargs": {"invert": true}},
            {"function": "filter_direct"},
            {"function": "filter_belief", "args": [0.95]}
            ]
        }

- `reading` : dict, optional
    Configuration of model update process. For more details see
    :ref:`reading_config`

- `test` : dict
    Configuration of model testing. For more details see
    :ref:`test_config`

- `query` : dict, optional
    Configuration of model queries. For more details see
    :ref:`query_config`

- `make_tests` : bool or dict, optional
    It is possible to create tests from model assembled statements to test
    other models against them. If set to True, then tests will be created
    from all assembled statements. For details on filtering the statements
    to a specific subset, see :ref:`make_tests_config`


.. _reading_config:

Model update configuration
--------------------------
Model update configuration is the value mapped to the key `reading` in the
model config. It defines the model update process. It can include the
following fields:

- `reader` : list[str], optional
    A list of readers to process the literature. Accepted elements are:
    `indra_db_pmid`, `indra_db_doi`, `elsevier_eidos`, `aws`. See
    :ref:`readers` for more information about readers.
    Default: ["indra_db_pmid"]

- `literature_source` : list[str], optional
    A list of sources to search the literature. Accepted elements are:
    `pubmed`, `biorxiv`, `elsevier`. Default: ["pubmed"]. Note that literature
    sources should be provided in the same order as the readers to read them.

- `cord19_update` : dict, optional
    COVID-19 specific configuration to update model from the CORD19 corpus. The
    dictionary should have the following fields:

        - `metadata` : dict
            Metadata to pass to new EmmaaStatements.

        - `date_limit`: int
            Number of days to search back.

    - Example:

    .. code-block:: json

        {"cord19_update": {
            "metadata": {
                "internal": true,
                "curated": false
                },
            "date_limit": 5
            }
        }

- `disease_map` : dict, optional
    A configuration to update a model from MINERVA Disease Map. It should have
    the following fields:

    - `map_name` : str
        A name of a disease_map.

    - `filenames` : list[str] or str
        A list of SIF filenames from the disease map to process or `all` to 
        process all filenames.

    - `metadata` : dict
        Metadata to pass to new EmmaaStatements.

    - Example:

    .. code-block:: json

        {"disease_map": {
            "map_name": "covid19map",
            "filenames" : "all",
            "metadata": {
                "internal": true
                }
            }
        }

- `other_files`: list[dict]
    A list of configurations to load statements from existing pickle files on
    S3. Each dictionary in the list should have the following fields:

    - `bucket` : str
        A name of S3 bucket.
    - `filename` : str
        A name of a pickle file.
    - `metadata` : str
        Metadata to pass to new EmmaaStatements loaded from this file.

    - Example:

    .. code-block:: json

        {"other_files": [
            {
                "bucket": "indra-covid19",
                "filename": "ctd_stmts.pkl",
                "metadata": {"internal": true, "curated": true}
            }
        ]
        }

- `filter` : dict, optional
    Configuration of a statement filter used for statistics generation (e.g.
    to not include external statements into statistics).
    The filter dictionary should have the following fields:

    - `conditions` : dict
        Conditions represented as key-value pairs that statements'
        metadata can be compared to.

    - `evid_policy`: str
        Policy for checking statement's evidence objects. If "all", then the
        function returns True only if all of statement's evidence objects meet
        the conditions. If "any", the function returns True as long as at
        least one of statement's evidences meets the conditions.

    - Example:

    .. code-block:: json

        {"filter": {
            "conditions": {"internal": true},
            "evid_policy": "any"
            }
        }


.. _test_config:

Model testing configuration
---------------------------
Model testing configuration is the value mapped to the key `test` in the
model config. It defines the model testing process. It can include the
following fields:

- `test_corpus` : list[str]
    A list of test corpora names that the model will be tested against daily.

    - Example : ["covid19_curated_tests", "covid19_mitre_tests"]

- `default_test_corpus` : str
    The name of the test corpus that will be loaded by default on the model
    page on the EMMAA dashboard.

    - Example : "large_corpus_tests"

- `mc_types` : list[str]
    A list of network types a model should be assembled into. For each of the
    model types, a ModelChecker instance will be created and used to find
    explanations to tests. Accepted elements are: `pysb`, `pybel`, 
    `signed_graph`, `unsigned_graph`, `dynamic`.

- `statement_checking` : dict, optional
    Maximum paths and maximum path length to limit test results. In the most
    general case the dictionary should have only two keys (`max_path_length`
    and `max_paths`) but it is also possible to set a custom configuration for
    one model type. In this case, a nested dictionary can be added with
    model type as a key and a simple dictionary with the same two keys as a
    value. Default: {"max_path_length": 5, "max_paths": 1}.

    - Example (adding a custom config to a model type):

    .. code-block:: json

        {"statement_checking": {
            "max_paths": 1,
            "max_path_length": 4,
            "pybel": {
                "max_paths": 1,
                "max_path_length": 10
                }
            }
        }

- `filters` : dict
    Configuration for applying semantic filters to the model checking process.
    It is represented as a dictionary mapping a test corpus name to a filter
    function name. The filter function should be defined in
    :ref:`filter_functions` and registered with `@register_filter('node')`
    decorator.

    - Example:

    .. code-block:: json

        {"filters": {
            "covid19_mitre_tests" : "filter_chem_mesh_go"
            }
        }

- `edge_filters` : dict
    Configuration to apply edge filters to the model checking process.
    It is represented as a dictionary mapping a test corpus name to an edge
    filter function name. Filter function should be defined in
    :ref:`filter_functions` and registered with `@register_filter('edge')`
    decorator.

    - Example:

    .. code-block:: json

        {"edge_filters": {
            "covid19_tests" : "filter_to_internal_edges"
            }
        }

.. _query_config:

Model queries configuration
---------------------------
Configuration for model queries represented as a dictionary keyed by the type
of query: `statement_checking` (source-target paths), `open_search`
(up/down-stream paths), `dynamic` (temporal properties), and `intervention`
(source-target dynamics). Configuration for `statement_checking` and
`open_search` queries is similar to the model test `statement_checking` format.
Same as in test config, it is possible to set different values for different
model types.

Configuration for `dynamic` and `intervention` queries has different fields 
(all optional):

- `use_kappa` : bool
    Determines the mode of the simulation. If True, uses `kappa`, otherwise,
    runs the ODE simulations. Default: False.

- `time_limit` : int
    Number of seconds to run the simulation for. Default: 200000.

- `num_times` : int
    Number of time points in the simulation plot. Default: 100.

- `num_sim` : int
    Number of simulations to run. This should be only provided if
    `hypothesis_tester` is not set. Default: 2.

- `hypothesis_tester` : dict; currently only for `dynamic`, not `intervention`.
    Configuration to test a hypothesis using random samples with adaptive size.
    If this is given, `num_sim` should not be provided. The `hypothesis_tester`
    dictionary should include the following keys: `alpha` (Type-I error limit,
    between 0 and 1), `beta` (Type-II error limit, between 0 and 1), `delta`
    (indifference parameter for interval around `prob` in both directions),
    `prob` (probability threshold for the hypothesis, between 0 and 1).

Having `dynamic` and `intervention` key in query config is required for a
model to be listed as an option for model selection on temporal properties
and source-target dynamics queries pages (for path-based queries all models
will be listed).

    - Example (all query types):

    .. code-block:: json

        {"statement_checking": {
            "max_paths": 5,
            "max_path_length": 4,
            "pybel": {
                "max_paths": 10,
                "max_path_length": 10
                }
            },
         "open_search": {
            "max_paths": 50,
            "max_path_length": 2
            },
         "dynamic": {
            "use_kappa": true,
            "time_limit": 100,
            "num_times": 100,
            "hypothesis_tester": {"alpha": 0.1,
                                  "beta": 0.1,
                                  "delta": 0.05,
                                  "prob": 0.8}
            },
         "intervention": {
            "use_kappa": true,
            "time_limit": 1000,
            "num_times": 100,
            "num_sim": 1
            },
        }

.. _make_tests_config:

Making tests from model configuration
-------------------------------------
Configuration to filter the statements before creating the tests (e.g. to make
tests from literature derived statements and skip curated). It is the value
mapped to the key `make_tests` in the model config (if you do not need to filter
the statements and want to make tests from all assembled statements, it is
enough to set `make_tests` to True).
To filter statements, the `make_tests` should be set to dictionary with the
key `filter` and the value should be another dictionary with the following fields:

- `conditions` : dict
    Conditions represented as key-value pairs that statements'
    metadata can be compared to.

- `evid_policy`: str
    Policy for checking statement's evidence objects. If "all", then the
    function returns True only if all of statement's evidence objects meet
    the conditions. If "any", the function returns True as long as at
    least one of statement's evidences meets the conditions.


    .. code-block:: json

        {"make_tests":
            {"filter": {
                "conditions": {"curated": false},
                "evid_policy": "any"
                }
            }
        }
