import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
import boto3
from botocore.exceptions import ClientError

# ===== CONFIGURATION =====
SECRET_ID = os.environ["SECRET_ID"]
SYSTEM = os.environ.get("SYSTEM", "AWS")
SGT_OFFSET = timezone(timedelta(hours=8))

# ===== GLOBAL CACHE WITH EXPIRY =====
_CACHE = {"secrets": None, "last_load": None}
CACHE_TTL_SECONDS = 3600  # Refresh secrets every hour

def _get_secrets():
    """Fetch secrets with basic TTL caching to handle rotations."""
    now = datetime.now(timezone.utc)
    if _CACHE["secrets"] and _CACHE["last_load"]:
        if (now - _CACHE["last_load"]).total_seconds() < CACHE_TTL_SECONDS:
            return _CACHE["secrets"]

    print(f"[SECRET] Refreshing secrets from: {SECRET_ID}")
    try:
        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=SECRET_ID)
        _CACHE["secrets"] = json.loads(resp["SecretString"])
        _CACHE["last_load"] = now
        return _CACHE["secrets"]
    except Exception as e:
        print(f"[ERROR] Could not load secrets: {e}")
        raise

# ===== UTILS =====
def utc_to_sgt(timestr):
    if not timestr: return "N/A"
    try:
        # Handles both Z and +00:00 formats
        dt = datetime.fromisoformat(timestr.replace("Z", "+00:00"))
        return dt.astimezone(SGT_OFFSET).strftime("%Y-%m-%d %H:%M:%S SGT")
    except: return timestr

def send_telegram(message):
    secrets = _get_secrets()
    token = secrets["TELEGRAM_TOKEN"]
    chat_id = secrets["TELEGRAM_CHAT_ID"]
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    
    # Redundancy: Use a tight timeout but allow for retry on failure
    with urllib.request.urlopen(req, timeout=8) as res:
        return res.status

# ===== FORMATTERS (Optimized) =====
def format_event(event):
    """Unified router and formatter."""
    source = event.get("source", "unknown")
    detail_type = event.get("detail-type", "")
    detail = event.get("detail", {})
    region = event.get("region", "global")
    time_str = utc_to_sgt(event.get("time") or detail.get("eventTime"))

    # Tampering Detection logic
    tamper_events = {"DeleteRecoveryPoint", "DeleteBackupVault", "StopBackupJob"}
    is_tamper = detail.get("eventName") in tamper_events

    if source == "aws.backup" and "State Change" in detail_type and detail.get("state") == "FAILED":
        job_type = "Restore" if "Restore" in detail_type else "Backup"
        return f"🚨 <b>{SYSTEM} {job_type} Failure</b>\n" \
               f"<b>ID:</b> {detail.get('backupJobId') or detail.get('restoreJobId')}\n" \
               f"<b>Res:</b> {detail.get('resourceArn') or 'N/A'}\n" \
               f"<b>Time:</b> {time_str}"

    if is_tamper:
        user = detail.get("userIdentity", {}).get("arn", "unknown")
        return f"⚠️ <b>{SYSTEM} Tampering Alert</b>\n" \
               f"<b>Action:</b> {detail.get('eventName')}\n" \
               f"<b>User:</b> {user}\n" \
               f"<b>IP:</b> {detail.get('sourceIPAddress')}\n" \
               f"<b>Time:</b> {time_str}"

    return f"ℹ️ <b>{SYSTEM} Notification</b>\n<b>Type:</b> {detail_type}\n<b>Time:</b> {time_str}"

# ===== MAIN HANDLER =====
def lambda_handler(event, context):
    print(f"[START] Processing {len(event.get('Records', []))} records")
    
    # Manual Test Support
    if event.get("manual_test"):
        send_telegram(f"✅ <b>{SYSTEM}</b> Connectivity Test Successful.")
        return {"status": "test_ok"}

    errors = []
    for record in event.get("Records", []):
        try:
            if record.get("EventSource") != "aws:sns":
                continue
                
            sns_msg = record["Sns"]["Message"]
            try:
                payload = json.loads(sns_msg)
            except json.JSONDecodeError:
                payload = {"detail-type": "Raw SNS", "detail": {"msg": sns_msg}}

            msg_text = format_event(payload)
            send_telegram(msg_text)
            
        except Exception as e:
            print(f"[ERROR] Record processing failed: {e}")
            errors.append(str(e))

    if errors:
        # Raising an error at the end ensures Lambda retries the batch 
        # (or sends to DLQ) if any message failed to send to Telegram.
        raise RuntimeError(f"Batch processed with {len(errors)} errors: {errors}")

    return {"status": "success"}
