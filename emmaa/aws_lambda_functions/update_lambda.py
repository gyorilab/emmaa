import boto3
import sys
from os import path
from zipfile import ZipFile

HERE = path.dirname(path.abspath(__file__))


def upload_function(script_name, function_name):
    """Upload the lambda function by pushing a zip file to Lambda.

    This function pre-supposes you are running from the same directory that
    contains the lambda script. 
    
    Parameters
    ----------
    script_name : str
        Name of a script containing lambda function. 
    function_name : object
        Name of a lambda function as specified on AWS Lambda.
    """
    lamb = boto3.client('lambda')
    with ZipFile(path.join(HERE, 'lambda.zip'), 'w') as zf:
        zf.write(path.join(HERE, script_name),
                 f'emmaa/{path.basename(HERE)}/{script_name}')
        zf.write(path.join(HERE, '__init__.py'),
                 f'emmaa/{path.basename(HERE)}/__init__.py')
        zf.write(path.join(HERE, path.pardir, '__init__.py'),
                 'emmaa/__init__.py')

    with open(path.join(HERE, 'lambda.zip'), 'rb') as zf:
        ret = lamb.update_function_code(ZipFile=zf.read(),
                                        FunctionName=function_name)
        print(ret)
    return

def main():
    script_name = sys.argv[1]
    function_name = sys.argv[2]
    upload_function(script_name, function_name)

if __name__ == '__main__':
    main()