- Model was initialized by first obtaining raw INDRA Statements for any articles
  in the INDRA DB with a matching ID (PMID, PMCID, DOI).
- These statements were combined with statements obtained from processing all
  full texts with Eidos; and those from the Gordon et al. host-virus
  interactions obtained via NDex.
- The resulting pickle file of combined statements was stored in
  s3://indra-covid19/cord19_combined_stmts.pkl
- Model upload script, upload.sh, in this directory
    - Uploads config.json (in this directory)
    - Generate EMMAA model pickle file from cord19_combined_stmts.pkl file
      via the script /emmaa/scripts/emmaa_model_from_stmts.py
    - Parameters for script:
      - short_name: covid19
      - full_name: Covid-19
      - indra_stmts: cord19_combined_stmts.pkl
      - ndex_id: blank on first load, afterwards set to
        a8c0decc-6bbb-11ea-bfdc-0ac135e8bacf

To run update cycle without using AWS Batch:

- python update_model_manager -m covid19

- Usually you will need to manually set the network style::

    from indra.databases.ndex_client import set_style
    set_style('a8c0decc-6bbb-11ea-bfdc-0ac135e8bacf')

- python run_model_stats_from_s3.py -m covid19 -s model -t covid19_curated_tests

- python run_model_tests_from_s3.py -m covid19 -t covid19_curated_tests

- python run_model_stats_from_s3.py -m covid19 -s tests -t covid19_curated_tests

