# Upload the config.json
aws s3 cp config.json s3://emmaa/models/covid19/config.json
# Upload the raw statement pickle file
python ../../scripts/emmaa_model_from_stmts.py -m covid19 -s ../../../covid-19/stmts/cord19_combined_stmts.pkl -c config.json

