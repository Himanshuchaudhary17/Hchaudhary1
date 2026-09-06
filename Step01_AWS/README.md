# Lab 01 - AWS Account Setup, IAM User, and MFA

## Access Key Confirmation

Access key successfully created for the IAM lab user.

Access Key ID: AKIA****...**** (last 4 characters: NYXJ)

The Secret Access Key is stored securely and is not included in this repository.

## Security Reflection

Securing the AWS root user with Multi-Factor Authentication is important because the root user has complete access to the AWS account, including billing and all cloud resources. If the root account is compromised, an attacker could create, modify, or delete resources and potentially cause unexpected charges.

For normal work, an IAM user should be used instead of the root user. IAM allows permissions to be controlled so that users receive only the access they need. This follows the principle of least privilege and reduces security risk if an account is compromised. Using MFA on both the root user and the IAM user adds an additional layer of protection beyond the password.
