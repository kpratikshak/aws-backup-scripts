"""
Lambda function to find and optionally delete stale EBS snapshots.

Environment variables:
- RETENTION_DAYS (int) : delete snapshots older than this many days (default: 30)
- DRY_RUN (str) : "true"/"false" - if true, don't actually delete (default: "true")
- EXCLUDE_TAG_KEY (str) : tag key to check to exclude snapshot from deletion (default "Keep")
- EXCLUDE_TAG_VALUE (str) : tag value which, if present with the key above, excludes snapshot (default "true")
- LOG_LEVEL (str) : logging level (DEBUG, INFO, WARNING, ERROR) default INFO

How it works:
- Lists snapshots owned by the current account.
- Filters snapshots by age (> RETENTION_DAYS) and state == 'completed'.
- Skips snapshots with the exclude tag key=value.
- Skips snapshots referenced by AMIs.
- If DRY_RUN is false, attempts to delete the snapshot.
"""

import os
import logging
import boto3
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

# Create AWS clients outside handler for re-use / performance
_ec2 = boto3.client("ec2")
_account_id = None  # lazily resolved

# Env defaults
def get_env_int(name, default):
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        raise ValueError(f"Environment variable {name} must be an integer, got {v!r}")

RETENTION_DAYS = get_env_int("RETENTION_DAYS", 30)
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("1", "true", "yes", "y")
EXCLUDE_TAG_KEY = os.getenv("EXCLUDE_TAG_KEY", "Keep")
EXCLUDE_TAG_VALUE = os.getenv("EXCLUDE_TAG_VALUE", "true")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig()
logger = logging.getLogger("stale-ebs-snapshots")
logger.setLevel(LOG_LEVEL)

def get_account_id():
    global _account_id
    if _account_id:
        return _account_id
    try:
        # STS get-caller-identity is reliable for account id
        sts = boto3.client("sts")
        _account_id = sts.get_caller_identity()["Account"]
        return _account_id
    except Exception as e:
        logger.warning("Failed to determine account id via STS: %s", e)
        return None

def snapshot_has_exclude_tag(snapshot):
    """Return True if snapshot has tag EXCLUDE_TAG_KEY=EXCLUDE_TAG_VALUE."""
    tags = snapshot.get("Tags") or []
    for t in tags:
        if t.get("Key") == EXCLUDE_TAG_KEY:
            # If no value specified and key exists, treat as excluded
            if EXCLUDE_TAG_VALUE == "" or t.get("Value", "").lower() == EXCLUDE_TAG_VALUE.lower():
                return True
    return False

def snapshot_used_by_any_ami(snapshot_id):
    """Return True if any AMI references this snapshot_id in its block device mappings."""
    try:
        # Describe images owned by self and others? We only need to check images owned by this account (likely)
        # Use Filters with 'block-device-mapping.snapshot-id' to find images referencing the snapshot
        resp = _ec2.describe_images(
            Owners=[get_account_id()] if get_account_id() else ["self"],
            Filters=[{
                "Name": "block-device-mapping.snapshot-id",
                "Values": [snapshot_id]
            }]
        )
        images = resp.get("Images", [])
        if images:
            logger.debug("Snapshot %s is referenced by AMI(s): %s", snapshot_id, [i.get("ImageId") for i in images])
            return True
        return False
    except ClientError as e:
        logger.warning("Failed to describe images for snapshot %s: %s", snapshot_id, e)
        # safest choice: treat as in-use to avoid accidental deletion when we can't confirm
        return True
    except Exception as e:
        logger.exception("Unexpected error checking AMI usage for snapshot %s: %s", snapshot_id, e)
        return True

def list_owned_snapshots():
    """Paginated listing of snapshots owned by the current account."""
    owner_id = get_account_id()
    paginator = _ec2.get_paginator("describe_snapshots")
    params = {}
    if owner_id:
        params["OwnerIds"] = [owner_id]
    else:
        params["OwnerIds"] = ["self"]
    for page in paginator.paginate(**params):
        for snap in page.get("Snapshots", []):
            yield snap

def should_delete_snapshot(snapshot, cutoff_dt):
    """
    Return (True/False, reason str) whether snapshot should be deleted.
    - Must be older than cutoff_dt
    - Must be in 'completed' state
    - Must not have exclude tag
    - Must not be referenced by any AMI
    """
    snap_id = snapshot["SnapshotId"]
    start_time = snapshot["StartTime"]
    state = snapshot.get("State", "").lower()

    if state != "completed":
        return False, f"state={state}"
    if not isinstance(start_time, datetime):
        return False, "no start time"
    if start_time.tzinfo is None:
        # make timezone-aware (assume UTC)
        start_time = start_time.replace(tzinfo=timezone.utc)

    if start_time > cutoff_dt:
        return False, f"age less than retention ({start_time.isoformat()})"

    if snapshot_has_exclude_tag(snapshot):
        return False, f"excluded by tag {EXCLUDE_TAG_KEY}={EXCLUDE_TAG_VALUE}"

    if snapshot_used_by_any_ami(snap_id):
        return False, "referenced by AMI"

    return True, "eligible"

def delete_snapshot(snapshot_id):
    """Delete a snapshot; returns (True, message) on success or (False, error_message)."""
    try:
        _ec2.delete_snapshot(SnapshotId=snapshot_id)
        return True, "deleted"
    except ClientError as e:
        # specific handling for dependency errors could be added
        logger.warning("ClientError deleting snapshot %s: %s", snapshot_id, e)
        return False, str(e)
    except Exception as e:
        logger.exception("Unexpected error deleting snapshot %s: %s", snapshot_id, e)
        return False, str(e)

def build_cutoff(retention_days):
    """Return timezone-aware cutoff datetime (UTC). Snapshots older than this are candidates."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)
    return cutoff

def handler(event, context):
    """
    Lambda entry point.
    Optionally supports a simple manual override via event:
      { "retention_days": 60, "dry_run": false }
    But environment variables take precedence if present.
    """
    # Allow event overrides, but environment variables are primary (explicit)
    retention_days = RETENTION_DAYS
    dry_run = DRY_RUN
    if isinstance(event, dict):
        if "retention_days" in event and not os.getenv("RETENTION_DAYS"):
            try:
                retention_days = int(event["retention_days"])
            except Exception:
                logger.warning("Invalid event retention_days %r", event["retention_days"])
        if "dry_run" in event and not os.getenv("DRY_RUN"):
            dry_run = bool(event["dry_run"])

    logger.info("Starting stale EBS snapshot cleanup: retention_days=%s, dry_run=%s, exclude_tag=%s=%s",
                retention_days, dry_run, EXCLUDE_TAG_KEY, EXCLUDE_TAG_VALUE)

    cutoff = build_cutoff(retention_days)
    logger.info("Deleting snapshots older than %s (UTC)", cutoff.isoformat())

    stats = {
        "total_scanned": 0,
        "eligible": 0,
        "deleted": 0,
        "skipped": 0,
        "errors": 0,
        "skipped_reasons": {}
    }

    for snap in list_owned_snapshots():
        stats["total_scanned"] += 1
        snap_id = snap.get("SnapshotId")
        try:
            eligible, reason = should_delete_snapshot(snap, cutoff)
            if not eligible:
                stats["skipped"] += 1
                stats["skipped_reasons"].setdefault(reason, 0)
                stats["skipped_reasons"][reason] += 1
                logger.debug("Skip %s: %s", snap_id, reason)
                continue

            stats["eligible"] += 1
            size_gb = snap.get("VolumeSize")
            description = snap.get("Description", "")
            start_time = snap.get("StartTime")
            logger.info("Eligible snapshot %s size=%sGB start_time=%s desc=%r", snap_id, size_gb, start_time, description)

            if dry_run:
                logger.info("[DRY_RUN] Would delete snapshot %s", snap_id)
                continue

            ok, msg = delete_snapshot(snap_id)
            if ok:
                stats["deleted"] += 1
                logger.info("Deleted snapshot %s", snap_id)
            else:
                stats["errors"] += 1
                logger.warning("Failed to delete snapshot %s: %s", snap_id, msg)

        except Exception as exc:
            logger.exception("Unhandled error processing snapshot %s: %s", snap_id, exc)
            stats["errors"] += 1

    logger.info("Completed. Scanned=%d Eligible=%d Deleted=%d Skipped=%d Errors=%d",
                stats["total_scanned"], stats["eligible"], stats["deleted"], stats["skipped"], stats["errors"])
    logger.debug("Skipped reasons: %s", stats["skipped_reasons"])

    # Return stats (useful for synchronous invocation)
    return stats


# If run as script (for local testing), call handler with dry-run defaults.
if __name__ == "__main__":
    import json
    # Basic local run
    event = {"retention_days": RETENTION_DAYS, "dry_run": DRY_RUN}
    res = handler(event, None)
    print(json.dumps(res, indent=2, default=str))
