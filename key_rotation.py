
# Python Shell Script #
# If the key has been active for 90 days, rotate it  and create a new one #
# If the key has been active for 83 days, send a one-week email reminder.#
# If the key has been active for 89 days, send a one-day email reminder. #
  
import datetime
from datetime import date
import dateutil
from dateutil import parser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import boto3
from botocore.exceptions import ClientError
iam_client = boto3.client('iam')
The following steps detail what the script does:


## Check the key age for each user with an active access key.

try:
    marker = None
    paginator = iam_client.get_paginator('list_users')
    # Need to use a paginator because by default API call only returns 100 records
    for page in paginator.paginate(PaginationConfig={'PageSize': 100, 'StartingToken': marker}):
        print("Next Page : {} ".format(page['IsTruncated']))
        u = page['Users']
        for user in u:
            keys = iam_client.list_access_keys(UserName=user['UserName'])
            for key in keys['AccessKeyMetadata']:
                active_for = date.today() - key['CreateDate'].date()
                # With active keys older than 90 days
                if key['Status']=='Active' and active_for.days >= 90:
                    print (user['UserName'] + " - " + key['AccessKeyId'] + " - " + str(active_for.days) + " days old. Rotating.")
                    delete_key(key['AccessKeyId'], user['UserName'])
                    create_key(user['UserName'])
                # Send a notification email 7 days before rotation
                elif key['Status']=='Active' and active_for.days == 83:
                    send_email("MAILBOX_EMAIL", "MAILBOX_PASSWORD", "recipient_email", subject_1_week, body_1_week)
                    print ("Email sent to " + user['UserName'] + " warning of key rotation in a week.")
                # Send a notification email 1 day before rotation
                elif key['Status']=='Active' and active_for.days == 89:
                    send_email("MAILBOX_EMAIL", "MAILBOX_PASSWORD", "recipient_email", subject_1_day, body_1_day)
                    print ("Email sent to " + user['UserName'] + " warning of key rotation tomorrow.")
