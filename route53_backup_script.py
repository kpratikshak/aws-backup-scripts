"""AWS Route 53 Lambda Backup"""

import os
import csv
import io
import json
import time
import logging
from datetime import datetime, timezone
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

# --- Logging ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Config (fail fast if missing) ---
def _require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    return value

S3_BUCKET_NAME = _require_env("s3_bucket_name")
S3_BUCKET_REGION = _require_env("s3_bucket_region")

# --- Boto3 clients (reused across warm Lambda invocations) ---
s3 = boto3.client("s3", region_name=S3_BUCKET_REGION)
route53 = boto3.client("route53")


# --- S3 ---

def ensure_s3_bucket(bucket_name: str, bucket_region: str) -> None:
    """Create the S3 bucket if it doesn't already exist."""
    try:
        s3.head_bucket(Bucket=bucket_name)
        logger.info("Bucket '%s' already exists.", bucket_name)
        return
    except ClientError as e:
        if e.response["Error"]["Code"] != "404":
            raise  # Surface unexpected errors immediately

    config = {} if bucket_region == "us-east-1" else {
        "CreateBucketConfiguration": {"LocationConstraint": bucket_region}
    }
    s3.create_bucket(Bucket=bucket_name, ACL="private", **config)
    logger.info("Created bucket '%s' in '%s'.", bucket_name, bucket_region)


def upload_bytes_to_s3(data: bytes, bucket: str, key: str) -> None:
    """Upload raw bytes directly to S3 — no temp file needed."""
    s3.put_object(Bucket=bucket, Key=key, Body=data)


# --- Route 53 ---

def get_hosted_zones() -> list:
    """Return all hosted zones using a paginator (cleaner than manual recursion)."""
    paginator = route53.get_paginator("list_hosted_zones")
    return [
        zone
        for page in paginator.paginate()
        for zone in page["HostedZones"]
    ]


def get_zone_records(zone_id: str) -> list:
    """Return all records for a hosted zone using a paginator."""
    paginator = route53.get_paginator("list_resource_record_sets")
    return [
        record
        for page in paginator.paginate(HostedZoneId=zone_id)
        for record in page["ResourceRecordSets"]
    ]


def get_record_value(record: dict) -> list:
    """Return a list of string values for a record (handles Alias and standard)."""
    alias = record.get("AliasTarget")
    if alias:
        return [f"ALIAS:{alias['HostedZoneId']}:{alias['DNSName']}"]
    return [r["Value"] for r in record.get("ResourceRecords", [])]


# --- Serialization (in-memory, no /tmp writes) ---

HEADERS = ["NAME", "TYPE", "VALUE", "TTL", "REGION",
           "WEIGHT", "SETID", "FAILOVER", "EVALUATE_HEALTH"]

def zone_to_csv_bytes(zone_records: list) -> bytes:
    """Serialize zone records to CSV bytes (in-memory)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADERS)

    for record in zone_records:
        alias_target = record.get("AliasTarget")
        base_row = [
            record["Name"],
            record["Type"],
            "",  # VALUE placeholder
            record.get("TTL", ""),
            record.get("Region", ""),
            record.get("Weight", ""),
            record.get("SetIdentifier", ""),
            record.get("Failover", ""),
            alias_target.get("EvaluateTargetHealth", "") if alias_target else "",
        ]
        for value in get_record_value(record):
            row = base_row.copy()
            row[2] = value
            writer.writerow(row)

    return buffer.getvalue().encode("utf-8")


def zone_to_json_bytes(zone_records: list) -> bytes:
    """Serialize zone records to JSON bytes (in-memory)."""
    return json.dumps(zone_records, indent=2).encode("utf-8")


# --- Handler ---

def lambda_handler(event, context):
    """Back up all Route 53 hosted zones to S3 as CSV and JSON."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ensure_s3_bucket(S3_BUCKET_NAME, S3_BUCKET_REGION)

    zones = get_hosted_zones()
    logger.info("Found %d hosted zone(s).", len(zones))

    for zone in zones:
        zone_name = zone["Name"].rstrip(".")
        zone_id = zone["Id"]
        folder = f"{timestamp}/{zone_name}"

        logger.info("Processing zone: %s", zone_name)
        records = get_zone_records(zone_id)

        upload_bytes_to_s3(
            zone_to_csv_bytes(records),
            S3_BUCKET_NAME,
            f"{folder}/{zone['Name']}csv",
        )
        upload_bytes_to_s3(
            zone_to_json_bytes(records),
            S3_BUCKET_NAME,
            f"{folder}/{zone['Name']}json",
        )

    logger.info("Backup complete. Timestamp: %s", timestamp)
    return {"status": "ok", "timestamp": timestamp, "zones_backed_up": len(zones)}


if __name__ == "__main__":
    lambda_handler({}, None)
