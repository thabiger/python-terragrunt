#
#  Copyright (c) 2022-2025 Tomasz Habiger and and contributors
#

import boto3
import botocore
import botocore.exceptions
import logging

logger = logging.getLogger(__name__)

class S3:
    @staticmethod
    def get(bucket_name, key):
        res = boto3.resource('s3')
        obj = res.Object(bucket_name, key)

        try:
            obj.load()
        except botocore.exceptions.ClientError as e:
            logger.error(f"Object '{key}' not found in S3 bucket s3://{bucket_name}: {e}")
            return None

        return obj.get()['Body'].read().decode('utf-8')
