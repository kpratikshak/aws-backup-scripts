import boto3
import logging
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Reuse STS client (cold start optimization)
sts_client = boto3.client('sts')


def assume_role(account_id: str, role_name: str) -> boto3.Session:
    try:
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="SQSQueueEncryptionSession"
        )
        creds = response['Credentials']

        return boto3.Session(
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
        )

    except ClientError as e:
        logger.error(f"Error assuming role for {account_id}: {e}")
        raise


def list_sqs_queues(sqs_client) -> List[str]:
    queue_urls = []
    paginator = sqs_client.get_paginator('list_queues')

    for page in paginator.paginate():
        queue_urls.extend(page.get('QueueUrls', []))

    return queue_urls


def is_queue_encrypted(sqs_client, queue_url: str) -> bool:
    try:
        response = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['KmsMasterKeyId']
        )
        return 'KmsMasterKeyId' in response.get('Attributes', {})

    except ClientError as e:
        logger.error(f"Error fetching attributes for {queue_url}: {e}")
        return True  # Skip on error to avoid breaking execution


def encrypt_sqs_queue(sqs_client, queue_url: str, kms_key_id: str) -> None:
    try:
        sqs_client.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={'KmsMasterKeyId': kms_key_id}
        )
        logger.info(f"Encrypted queue: {queue_url}")

    except ClientError as e:
        logger.error(f"Failed to encrypt {queue_url}: {e}")


def process_queue(sqs_client, queue_url: str, kms_key_id: str):
    if not is_queue_encrypted(sqs_client, queue_url):
        encrypt_sqs_queue(sqs_client, queue_url, kms_key_id)


def process_account(account_id: str, role_name: str, kms_key_id: str) -> None:
    session = assume_role(account_id, role_name)
    sqs_client = session.client('sqs')

    queue_urls = list_sqs_queues(sqs_client)

    if not queue_urls:
        logger.info(f"No queues found in account {account_id}")
        return

    # Parallel processing (tune max_workers based on Lambda memory)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(process_queue, sqs_client, q, kms_key_id)
            for q in queue_urls
        ]

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Thread execution failed: {e}")
