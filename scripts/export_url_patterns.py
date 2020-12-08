import sys
import json
from indra.databases import get_identifiers_url
from emmaa.model_tests import load_model_manager_from_s3


if __name__ == '__main__':
    model_name = sys.argv[1]
    mm = load_model_manager_from_s3(model_name)
    namespaces = set()
    for entity in mm.entities:
        namespaces |= set(entity.db_refs)
    namespaces -= {'TEXT', 'TEXT_NORM'}
    namespaces = sorted(namespaces)
    urls = {ns: get_identifiers_url(ns, '[ID]') for ns in namespaces}
    urls = {k: v for k, v in urls.items() if v is not None}
    # Some INDRA-specific customizations we need to revert here
    if 'CHEBI' in urls:
        urls['CHEBI'] = urls['CHEBI'].replace('CHEBI:', '')
    if 'CHEMBL' in urls:
        urls['CHEMBL'] = urls['CHEMBL'].replace('CHEMBL', '')
    with open('url_patterns.json', 'w') as fh:
        json.dump(urls, fh, indent=1)