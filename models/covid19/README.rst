- Model was initialized by first obtaining raw INDRA Statements for any articles
  in the INDRA DB with a matching ID (PMID, PMCID, DOI).
- These statements were combined with statements obtained from processing all
  full texts with Eidos; and those from the Gordon et al. host-virus
  interactions obtained via NDex.
- The resulting pickle file of combined statements was stored in
  s3://indra-covid19/cord19_combined_stmts.pkl
- Model upload script, upload.sh, in this directory
    - This pickle file was used to create
      a model via the script /emmaa/scripts/emmaa_model_from_stmts.py
    - Parameters for script:
      - short_name: covid19
      - full_name: Covid-19
      - indra_stmts: cord19_combined_stmts.pkl
      - ndex_id: 
    - Upload config.json (in this directory)
#- python run_model_stats_from_s3.py -m covid19 -s model -t covid19_curated_tests
#- python run_model_tests_from_s3.py -m covid19 -t covid19_curated_tests
