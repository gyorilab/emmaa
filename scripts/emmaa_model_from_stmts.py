import json
import boto3
import argparse
import datetime
from indra.databases import ndex_client
from indra.assemblers.cx import CxAssembler
from indra.tools import assemble_corpus as ac
from emmaa.model import EmmaaModel, save_config_to_s3
from emmaa.statements import to_emmaa_stmts


def create_upload_model(model_name, indra_stmts, config_file):
    """Make and upload an EMMAA model from a list of INDRA Statements.

    Parameters
    ----------
    short_name : str
        Short name of the model to use on S3.
    indra_stmts : list of indra.statement
        INDRA Statements to be used to populate the EMMAA model.
    ndex_id : str
        UUID of the network corresponding to the model on NDex. If provided,
        the NDex network will be updated with the latest model content.
        If None (default), a new network will be created and the UUID stored
        in the model config files on S3.
    """
    emmaa_stmts = to_emmaa_stmts(indra_stmts, datetime.datetime.now(), [])
    # Load config information
    with open(config_file, 'rt') as f:
        config_json = json.load(f)
    # If there is no ndex entry in the config, create a new network and update
    # the config file with the NDex network ID
    if 'ndex' not in config_json:
        cxa = CxAssembler(indra_stmts)
        cx_str = cxa.make_model()
        ndex_id = cxa.upload_model(private=False)
        print(f'NDex ID for {model_name} is {ndex_id}.')
        config_json['ndex'] = {'network': ndex_id}
        updated_config_file = f'{config_file}.updated'
        with open(updated_config_file, 'wt') as f:
            json.dump(config_json, f, indent=2)
    # If the NDEx ID is provided we don't need to update the existing network
    # because this will occur as part of the model assembly/update procedure
    # on EMMAA itself.
    # Create the config dictionary
    # Create EMMAA model
    emmaa_model = EmmaaModel(model_name, config_json)
    emmaa_model.add_statements(emmaa_stmts)
    # Upload model to S3
    emmaa_model.save_to_s3()
    # Upload config JSON
    s3_client = boto3.client('s3')
    save_config_to_s3(model_name, config_dict)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
         description='Create and upload an EMMAA model from INDRA Statements.')
    parser.add_argument('-m', '--model_name', help='Model (short) name',
                        required=True)
    parser.add_argument('-s', '--stmt_pkl', help='Statement pickle file',
                        required=True)
    parser.add_argument('-c', '--config', help='Config JSON file',
                        required=True)
    args = parser.parse_args()

    # Load the statements
    indra_stmts = ac.load_statements(args.stmt_pkl)

    # Create the model
    create_upload_model(args.model_name, indra_stmts, args.config)

