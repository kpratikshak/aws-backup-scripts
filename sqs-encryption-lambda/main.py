import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from functions import process_account

# Configure logging once (Lambda best practice)
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def validate_input(accounts: List[str], role_name: str, kms_key_id: str):
    if not accounts:
        raise ValueError("Accounts list cannot be empty")
    if not role_name:
        raise ValueError("Role name is required")
    if not kms_key_id:
        raise ValueError("KMS Key ID is required")


def process_accounts_parallel(accounts: List[str], role_name: str, kms_key_id: str):
    results = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(process_account, acc, role_name, kms_key_id): acc
            for acc in accounts
        }

        for future in as_completed(futures):
            account_id = futures[future]
            try:
                future.result()
                logger.info(f"Successfully processed account: {account_id}")
                results.append({"account": account_id, "status": "success"})
            except Exception as e:
                logger.error(f"Failed for account {account_id}: {e}")
                results.append({"account": account_id, "status": "failed", "error": str(e)})

    return results


# ✅ Lambda Handler
def lambda_handler(event, context):
    """
    Expected event format:
    {
        "accounts": ["123456789012", "987654321098"],
        "role_name": "CrossAccountRole",
        "kms_key_id": "alias/aws/sqs"
    }
    """

    try:
        accounts = event.get("accounts") or os.getenv("ACCOUNTS", "").split(",")
        role_name = event.get("role_name") or os.getenv("ROLE_NAME")
        kms_key_id = event.get("kms_key_id") or os.getenv("KMS_KEY_ID")

        validate_input(accounts, role_name, kms_key_id)

        logger.info(f"Starting processing for {len(accounts)} accounts")

        results = process_accounts_parallel(accounts, role_name, kms_key_id)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Processing completed",
                "results": results
            })
        }

    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


# ✅ Optional CLI support (for local testing)
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Encrypt SQS queues across accounts")
    parser.add_argument('--accounts', '-a', nargs='+', required=True)
    parser.add_argument('--role-name', '-r', required=True)
    parser.add_argument('--kms-key-id', '-k', required=True)

    args = parser.parse_args()

    validate_input(args.accounts, args.role_name, args.kms_key_id)

    process_accounts_parallel(args.accounts, args.role_name, args.kms_key_id)


if __name__ == "__main__":
    main()
