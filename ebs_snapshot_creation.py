import boto3
import datetime

# Replace the ARN with your SNS topic ARN
SNS_TOPIC_ARN = 'arn:aws:sns:us-west-2:123456789012:MyEBSSnapshots'

def create_snapshot_and_notify(volume_id):
    ec2 = boto3.resource('ec2')
    volume = ec2.Volume(volume_id)

    snapshot = volume.create_snapshot(
        Description=f'Snapshot of {volume_id} on {datetime.datetime.now()}'
    )

    sns = boto3.client('sns')
    response = sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Message=f'Snapshot {snapshot.id} created for volume {volume_id}',
        Subject='EBS Snapshot Created'
    )

    return response

def lambda_handler(event, context):
    VOLUME_IDS = event['volume_ids']

    for volume_id in VOLUME_IDS:
        create_snapshot_and_notify(volume_id)
