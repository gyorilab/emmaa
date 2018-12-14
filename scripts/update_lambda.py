import boto3


def upload_function():
    """Upload the lambda function by placing it on s3.
    
    This function pre-supposes you are running from the same directory that
    contains the lambda script, which should be named: `lambda_script.py`.
    """
    s3 = boto3.client('s3')
    with open('lambda_script.py', 'rb') as f:
        s3.put_object(f, Bucket='emmaa', Key='lambda_script.py')
    return


if __name__ == '__main__':
    upload_function()
