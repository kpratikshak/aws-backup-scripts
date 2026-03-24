import boto3
import time
from botocore.exceptions import ClientError

# ==============================
# Configuration
# ==============================
DB_CLUSTER_ID = "my-aurora-cluster"
DB_INSTANCE_ID = "my-aurora-instance"
DB_PASSWORD = "YourSecurePassword123!"
DB_USER = "admin"
SG_NAME = "aurora-public-sg"

REGION = "us-east-1"  # Change if needed

# ==============================
# AWS Clients
# ==============================
ec2 = boto3.client("ec2", region_name=REGION)
rds = boto3.client("rds", region_name=REGION)


def get_default_vpc():
    """Fetch default VPC ID"""
    response = ec2.describe_vpcs(
        Filters=[{"Name": "isDefault", "Values": ["true"]}]
    )
    return response["Vpcs"][0]["VpcId"]


def create_security_group(vpc_id):
    """Create or reuse security group"""
    try:
        sg = ec2.create_security_group(
            GroupName=SG_NAME,
            Description="Allow MySQL traffic from public internet",
            VpcId=vpc_id
        )
        sg_id = sg['GroupId']
        print(f"Security Group Created: {sg_id}")

        # Add inbound rule
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                'IpProtocol': 'tcp',
                'FromPort': 3306,
                'ToPort': 3306,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            }]
        )

    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            sg_id = ec2.describe_security_groups(
                GroupNames=[SG_NAME]
            )['SecurityGroups'][0]['GroupId']
            print(f"Using existing Security Group: {sg_id}")
        else:
            raise e

    return sg_id


def create_aurora_resources():
    """Main function to create Aurora cluster + instance"""

    vpc_id = get_default_vpc()
    sg_id = create_security_group(vpc_id)

    # Create DB Cluster
    print("Creating Aurora DB Cluster (this may take a few minutes)...")
    try:
        rds.create_db_cluster(
            DBClusterIdentifier=DB_CLUSTER_ID,
            Engine='aurora-mysql',
            MasterUsername=DB_USER,
            MasterUserPassword=DB_PASSWORD,
            VpcSecurityGroupIds=[sg_id],
            BackupRetentionPeriod=1,
            DeletionProtection=False
        )
    except ClientError as e:
        if "DBClusterAlreadyExistsFault" in str(e):
            print("Cluster already exists. Skipping creation.")
        else:
            raise e

    # Create DB Instance
    print(f"Creating Instance {DB_INSTANCE_ID}...")
    try:
        rds.create_db_instance(
            DBInstanceIdentifier=DB_INSTANCE_ID,
            DBClusterIdentifier=DB_CLUSTER_ID,
            Engine='aurora-mysql',
            DBInstanceClass='db.r5.large',
            PubliclyAccessible=True
        )
    except ClientError as e:
        if "DBInstanceAlreadyExists" in str(e):
            print("Instance already exists. Skipping creation.")
        else:
            raise e

    # Wait for availability
    print("Waiting for instance to become available...")
    waiter = rds.get_waiter('db_instance_available')
    waiter.wait(DBInstanceIdentifier=DB_INSTANCE_ID)

    # Fetch endpoint
    cluster_info = rds.describe_db_clusters(
        DBClusterIdentifier=DB_CLUSTER_ID
    )
    endpoint = cluster_info['DBClusters'][0]['Endpoint']

    print("\n" + "=" * 40)
    print("SUCCESS! Aurora Cluster is ready.")
    print(f"Writer Endpoint: {endpoint}")
    print(f"Username: {DB_USER}")
    print(f"Password: {DB_PASSWORD}")
    print("=" * 40)


# ==============================
# Entry Point
# ==============================
if __name__ == "__main__":
    create_aurora_resources()
