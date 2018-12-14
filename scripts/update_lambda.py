import boto3
from zipfile import ZipFile


def upload_function():
    """Upload the lambda function by pushing a zip :ile to Lambda.
    
    This function pre-supposes you are running from the same directory that
    contains the lambda script, which should be named: `lambda_script.py`.
    """
    lamb = boto3.client('lambda')
    with ZipFile('lambda.zip', 'w') as zf:
        zf.write('lambda_script.py')

    with open('lambda.zip', 'rb') as zf:
        lamb.update_function_code(ZipFile=zf.read(),
                                  FunctionName='emmaa-analysis')
    return


if __name__ == '__main__':
    upload_function()
