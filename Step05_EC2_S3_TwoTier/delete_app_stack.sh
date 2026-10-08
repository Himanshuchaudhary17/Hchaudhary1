#!/bin/bash
set -e
cd "$(dirname "$0")"
set -a
source .env
set +a

echo "== Terminating EC2 instances =="

if [[ -f uploader_instance_id.txt && -f viewer_instance_id.txt ]]; then
  UPLOADER_ID=$(cat uploader_instance_id.txt)
  VIEWER_ID=$(cat viewer_instance_id.txt)

  aws ec2 terminate-instances \
    --instance-ids "$UPLOADER_ID" "$VIEWER_ID" \
    --region "$AWS_REGION"

  aws ec2 wait instance-terminated \
    --instance-ids "$UPLOADER_ID" "$VIEWER_ID" \
    --region "$AWS_REGION"

  echo "Both EC2 instances terminated."
  rm -f uploader_instance_id.txt viewer_instance_id.txt
else
  echo "Instance ID files missing; check AWS manually."
  exit 1
fi

echo "== Deleting launch templates =="

aws ec2 delete-launch-template \
  --launch-template-name "$UPLOADER_LT_NAME" \
  --region "$AWS_REGION" 2>/dev/null || true

aws ec2 delete-launch-template \
  --launch-template-name "$VIEWER_LT_NAME" \
  --region "$AWS_REGION" 2>/dev/null || true

echo "Launch template cleanup finished."

echo "== Removing IAM profiles and roles =="

aws iam remove-role-from-instance-profile \
  --instance-profile-name "$UPLOADER_PROFILE_NAME" \
  --role-name "$UPLOADER_ROLE_NAME" 2>/dev/null || true

aws iam delete-instance-profile \
  --instance-profile-name "$UPLOADER_PROFILE_NAME" 2>/dev/null || true

aws iam delete-role-policy \
  --role-name "$UPLOADER_ROLE_NAME" \
  --policy-name uploader-put-only 2>/dev/null || true

aws iam delete-role \
  --role-name "$UPLOADER_ROLE_NAME" 2>/dev/null || true

aws iam remove-role-from-instance-profile \
  --instance-profile-name "$VIEWER_PROFILE_NAME" \
  --role-name "$VIEWER_ROLE_NAME" 2>/dev/null || true

aws iam delete-instance-profile \
  --instance-profile-name "$VIEWER_PROFILE_NAME" 2>/dev/null || true

aws iam delete-role-policy \
  --role-name "$VIEWER_ROLE_NAME" \
  --policy-name viewer-read-only 2>/dev/null || true

aws iam delete-role \
  --role-name "$VIEWER_ROLE_NAME" 2>/dev/null || true

echo "IAM cleanup finished."

echo "== Emptying and deleting S3 bucket =="

aws s3 rm "s3://$BUCKET_NAME" \
  --recursive \
  --region "$AWS_REGION"

aws s3api delete-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$AWS_REGION"

echo "Cleanup complete."
