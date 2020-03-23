- Model was initialized by first obtaining INDRA Statements for the PMC
  articles in the INDRA DB, filtering evidence to only those sentences that
  from the corpus.
- Resulting pickle files were stored in s3://indra-covid19/
- File s3://indra-covid19/cord19_pmc_stmts_filt.pkl was used to create
  an initial model via the script /emmaa/scripts/emmaa_model_from_stmts.py
- Parameters for script:
  - short_name: covid19
  - full_name: Covid-19
  - indra_stmts: cord19_pmc_stmts_filt.pkl
  - ndex_id: None
- Run model upload (upload.sh, in this directory)
- Upload config.json (in this directory)


- python run_model_stats_from_s3.py -m covid19 -s model -t covid19_curated_tests
- python run_model_tests_from_s3.py -m covid19 -t covid19_curated_tests
