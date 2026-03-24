#!/bin/bash

# Replace certificate_arn with the ARN of the SSL/TLS certificate you want to check
certificate_arn=”arn:aws:acm:us-east-1:123456789012:certificate/12345678–1234–1234–1234–123456789012"

# Get the expiration date of the SSL/TLS certificate
expiration_date=$(aws acm describe-certificate — certificate-arn $certificate_arn | jq -r ‘.Certificate.NotAfter’)

# Convert the expiration date to a timestamp
expiration_timestamp=$(date -d “$expiration_date” +%s)

# Get the current date and convert it to a timestamp
now=$(date +%s)

# Calculate the number of days until the certificate expires
days_until_expiration=$(( (expiration_timestamp — now) / 86400 ))

# If the number of days until expiration is less than or equal to the threshold, publish a message to the SNS topic
if [ “$days_until_expiration” -le 30 ]
then
aws sns publish — topic-arn topic_arn — message “SSL/TLS certificate $certificate_arn will expire in $days_until_expiration days.”
fi
