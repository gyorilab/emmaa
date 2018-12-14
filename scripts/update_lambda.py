import boto3
from zipfile import ZipFile


def upload_function():
    """Upload the lambda function by placing it on s3.
    
    This function pre-supposes you are running from the same directory that
    contains the lambda script, which should be named: `lambda_script.py`.
    """
    s3 = boto3.client('s3')
    with ZipFile('lambda.zip', 'w') as zf:
        zf.write('lambda_script.py')

    with open('lambda.zip', 'rb') as zf:
        s3.put_object(Body=zf, Bucket='emmaa', Key='lambda.zip')
    return


if __name__ == '__main__':
    upload_function()
