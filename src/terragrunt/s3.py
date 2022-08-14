import boto3
import botocore
import logging

logger = logging.getLogger(__name__)

s3 = boto3.resource('s3')
client = boto3.client('s3')

def get(bucket_name, key):

    obj = s3.Object(bucket_name, key)

    try:
        obj.load()
    except botocore.exceptions.ClientError as e:
        logger.debug("Object not found in S3 bucket")
        return None

    return obj.get()['Body'].read().decode('utf-8')

def list(bucket_name, prefix):

    o = []
    response = client.list_objects(Bucket=bucket_name, Prefix=prefix)
    try:
        for r in response['Contents']:
            o.append(r['Key'])
    except KeyError:
        logger.info("Missing TF state")

    return o