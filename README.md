# AWS Backup & Resource Management Automation

A collection of Python-based automation scripts leveraging the **AWS Boto3 SDK** to streamline the backup lifecycle, resource management, and cost optimization within an AWS environment.

## 🚀 Project Overview:

In a production environment, manual backups are prone to human error and inconsistency. This project provides a suite of scripts designed to automate the creation, retention, and cleanup of backups across various AWS services. These scripts are designed to be run locally, via CRON jobs, or as AWS Lambda functions.

## ✨ Key Features:

* **Automated EBS Snapshots:** Creates snapshots of EBS volumes based on specific tags (e.g., `Backup=True`).
* **S3 Data Synchronization:** Automates the backup of critical S3 bucket content to secondary regions for disaster recovery.
* **Retention Management:** Automatically identifies and deletes snapshots or backups older than a defined threshold (e.g., 30 days) to optimize storage costs.
* **RDS Snapshot Automation:** Triggers manual snapshots for RDS instances before major updates or as part of a custom backup schedule.
* **Error Logging & Reporting:** Integrated error handling to ensure visibility into failed backup operations.

## 🛠 Tech Stack:

* **Language:** Python 3.x
* **SDK:** AWS SDK for Python (Boto3)
* **Cloud Provider:** Amazon Web Services (AWS)
* **Services Handled:** EC2 (EBS), S3, RDS, IAM

## 📋 Prerequisites:

Before running the scripts, ensure you have the following:

1. **Python 3.x** installed.
2. **AWS CLI** configured with appropriate credentials.
```bash
aws configure
```


3. **Required Permissions:** The IAM user/role running these scripts must have permissions for `ec2:CreateSnapshot`, `ec2:DescribeVolumes`, `ec2:DeleteSnapshot`, `s3:PutObject`, etc.

## ⚙️ Installation & Setup

1. **Clone the Repository:**
```bash
git clone https://github.com/kpratikshak/aws-backup-scripts.git
cd aws-backup-scripts

```


2. **Install Dependencies:**
```bash
pip install -r requirements.txt

```
*(Note: Create a requirements.txt file including `boto3`)*

## 📖 Usage Examples:

### 1. EBS Backup Script

To create snapshots for all volumes tagged with `Backup: True`:

```bash
python ebs_backup.py

```

### 2. Cleanup Old Snapshots

To delete snapshots older than 30 days to save on storage costs:

```bash
python cleanup_snapshots.py --days 30

```

## 📂 Project Structure:

```text
aws-backup-scripts/
├── ebs_backup.py           # Logic for EBS snapshot creation
├── s3_sync_backup.py       # S3 bucket-to-bucket sync script
├── rds_manual_snapshot.py  # RDS backup automation
├── cleanup_manager.py      # Retention policy and deletion logic
├── utils/
│   └── aws_session.py      # Boto3 session and client helpers
└── requirements.txt        # Project dependencies

```

## 🤝 Contributing

Contributions are welcome! If you have ideas for new automation scripts or improvements to existing ones, feel free to open an issue or submit a pull request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.

## 👤 Author

**Pratiksha Kadam**

* **GitHub:** [@kpratikshak](https://www.google.com/search?q=https://github.com/kpratikshak)
* **LinkedIn:** [Pratiksha Kadam](https://www.google.com/search?q=https://linkedin.com/in/pratiksha-kadam-7706a3226)
