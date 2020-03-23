import pickle
from indra.sources import reach
from indra.statements import *
from emmaa.util import get_s3_client
from emmaa.model_tests import StatementCheckingTest, EMMAA_BUCKET_NAME

text = 'TBK1 activates IFNB1.'

rp = reach.process_text(text)
stmts = rp.statements
emmaa_tests = [StatementCheckingTest(s) for s in stmts]

client = get_s3_client(unsigned=False)
client.put_object(
        Body=pickle.dumps(emmaa_tests), Bucket=EMMAA_BUCKET_NAME,
        Key=f'tests/covid19_curated_tests.pkl')
