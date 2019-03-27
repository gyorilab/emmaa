import argparse
import datetime
import yaml
import json
import boto3
from indra.databases import ndex_client
from indra.assemblers.cx import CxAssembler
from indra.tools import assemble_corpus as ac
from emmaa.model import EmmaaModel
from emmaa.priors import SearchTerm
from emmaa.statements import to_emmaa_stmts


def create_upload_model(model_name, indra_stmts, ndex_id=None):
    emmaa_stmts = to_emmaa_stmts(indra_stmts, datetime.datetime.now(), [])
    # Get updated CX content for the INDRA Statements
    cxa = CxAssembler(indra_stmts)
    cx_str = cxa.make_model()
    # If we don't have an NDex ID, create network and upload to Ndex
    if ndex_id is None:
        ndex_id = cxa.upload_model(private=False)
        print(f'NDex ID for {model_name} is {ndex_id}.')
    # If the NDEx ID is provided, update the existing network
    else:
        ndex_client.update_network(cx_str, ndex_id)
    # Create the config dictionary
    config_dict = {'ndex': {'network': ndex_id},
                   'search_terms': []}
    # Create EMMAA model
    emmaa_model = EmmaaModel(model_name, config_dict)
    emmaa_model.add_statements(emmaa_stmts)
    # Upload model to S3 with config as YAML and JSON
    emmaa_model.save_to_s3()
    s3_client = boto3.client('s3')
    config_yaml = yaml.dump(config_dict)
    s3_client.put_object(Body=config_yaml.encode('utf8'),
                         Key='models/%s/config.yaml' % model_name,
                         Bucket='emmaa')
    config_json = json.dumps(config_dict)
    s3_client.put_object(Body=config_json.encode('utf8'),
                         Key='models/%s/config.json' % model_name,
                         Bucket='emmaa')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Create and upload an EMMAA model from INDRA Statements.')
    parser.add_argument('-m', '--model_name', help='Model name', required=True)
    parser.add_argument('-s', '--stmt_pkl', help='Statement pickle file',
                        required=True)
    parser.add_argument('-n', '--ndex_id',
                        help='NDex ID. If not given, a new NDEx network will '
                             'be created. If given, will update the NDEx '
                             'network.', required=False)
    args = parser.parse_args()

    # Load the statements
    indra_stmts = ac.load_statements(args.stmt_pkl)

    # Create the model
    create_upload_model(args.model_name, indra_stmts, args.ndex_id)

