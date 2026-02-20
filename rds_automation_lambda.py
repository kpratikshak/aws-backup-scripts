"""
AWS RDS Management Lambda Function

This module provides functionality to automatically start and stop RDS instances
based on configurable tags, time of day, and day of the week. It is designed to
run as an AWS Lambda function for cost optimization.
"""

import boto3
import datetime
from dateutil import tz
import logging
import os

# Configure logging to display informational messages
logging.basicConfig(level=logging.INFO)

# Set AWS region from environment variable, default to 'us-east-1'
region = os.getenv("AWS_REGION", "us-east-1")

# Create AWS RDS client using the specified region
rds = boto3.client('rds', region_name=region)

# Define required tags for RDS instances to be managed
# Tags are configurable via environment variables TAG_KEY and TAG_VALUE
REQUIRED_TAGS = {
    os.getenv("TAG_KEY", "Environment"): os.getenv("TAG_VALUE", "Production")
}

# Set timezone from environment variable, default to UTC
TIMEZONE = tz.gettz(os.getenv("TIMEZONE", "UTC"))
def get_tagged_rds_instances():
    """Fetches RDS instances with required tags."""
    try:
        # Retrieve all DB instances from AWS RDS
        instances = rds.describe_db_instances()['DBInstances']
        tagged_instances = []
        for db in instances:
            # Get tags for the current DB instance
            tags = rds.list_tags_for_resource(ResourceName=db['DBInstanceArn'])['TagList']
            # Convert tag list to dictionary for easy lookup
            tag_dict = {tag['Key']: tag['Value'] for tag in tags}
            # Check if all required tags match the instance's tags
            if all(REQUIRED_TAGS[key] == tag_dict.get(key, "") for key in REQUIRED_TAGS):
                tagged_instances.append(db['DBInstanceIdentifier'])
        return tagged_instances
    except Exception as e:
        logging.error(f"Error fetching RDS instances: {str(e)}")
        return []
def lambda_handler(event, context):
    """Lambda function to start/stop RDS based on time and day."""
    # Get current time in the configured timezone
    now = datetime.datetime.now(tz=TIMEZONE)
    current_hour = now.hour
    current_day = now.weekday()
    # Retrieve list of RDS instances that have the required tags
    tagged_rds_instances = get_tagged_rds_instances()
    for db_identifier in tagged_rds_instances:
        if 0 <= current_day <= 4:  # Weekdays (Monday-Friday)
            if 6 <= current_hour < 18:  # Business hours (6 AM to 6 PM)
                logging.info(f"Starting RDS {db_identifier}...")
                rds.start_db_instance(DBInstanceIdentifier=db_identifier)
            else:  # Outside business hours
                logging.info(f"Stopping RDS {db_identifier}...")
                rds.stop_db_instance(DBInstanceIdentifier=db_identifier)
        else:  # Weekends (Saturday-Sunday)
            logging.info(f"Stopping RDS {db_identifier} for the weekend...")
            rds.stop_db_instance(DBInstanceIdentifier=db_identifier)
    return "Lambda execution completed."
