#!/bin/bash
set -e
cd "$(dirname "$0")"

set -a
source .env

if [[ -f stack_outputs.env ]]; then
  source stack_outputs.env
else
  echo "stack_outputs.env not found."
  echo "Run create_app_stack.sh before running cleanup."
  exit 1
fi

set +a


echo "== Deleting Auto Scaling Groups =="

aws autoscaling delete-auto-scaling-group \
  --auto-scaling-group-name "$UPLOADER_ASG_NAME" \
  --force-delete \
  --region "$AWS_REGION" 2>/dev/null || true

aws autoscaling delete-auto-scaling-group \
  --auto-scaling-group-name "$VIEWER_ASG_NAME" \
  --force-delete \
  --region "$AWS_REGION" 2>/dev/null || true


echo "Waiting for both Auto Scaling Groups to be deleted..."

for ASG_NAME in "$UPLOADER_ASG_NAME" "$VIEWER_ASG_NAME"; do

  for i in $(seq 1 20); do

    EXISTING=$(aws autoscaling describe-auto-scaling-groups \
      --auto-scaling-group-names "$ASG_NAME" \
      --region "$AWS_REGION" \
      --query "AutoScalingGroups[0].AutoScalingGroupName" \
      --output text 2>/dev/null)

    if [[ "$EXISTING" == "None" || -z "$EXISTING" ]]; then
      echo "$ASG_NAME deleted."
      break
    fi

    echo "Waiting for $ASG_NAME..."
    sleep 15

  done
done


echo "== Deleting Application Load Balancer =="

aws elbv2 delete-load-balancer \
  --load-balancer-arn "$ALB_ARN" \
  --region "$AWS_REGION" 2>/dev/null || true

echo "Waiting for load balancer to be deleted..."

aws elbv2 wait load-balancers-deleted \
  --load-balancer-arns "$ALB_ARN" \
  --region "$AWS_REGION" 2>/dev/null || true


echo "== Deleting target groups =="

aws elbv2 delete-target-group \
  --target-group-arn "$UPLOADER_TG_ARN" \
  --region "$AWS_REGION" 2>/dev/null || true

aws elbv2 delete-target-group \
  --target-group-arn "$VIEWER_TG_ARN" \
  --region "$AWS_REGION" 2>/dev/null || true


echo "== Restoring app security group =="

aws ec2 revoke-security-group-ingress \
  --group-id "$APP_SECURITY_GROUP_ID" \
  --protocol tcp \
  --port 3000 \
  --source-group "$ALB_SECURITY_GROUP_ID" \
  --region "$AWS_REGION" >/dev/null 2>&1 || true

aws ec2 authorize-security-group-ingress \
  --group-id "$APP_SECURITY_GROUP_ID" \
  --protocol tcp \
  --port 3000 \
  --cidr 0.0.0.0/0 \
  --region "$AWS_REGION" >/dev/null 2>&1 || true


echo "== Deleting ALB security group =="

aws ec2 delete-security-group \
  --group-id "$ALB_SECURITY_GROUP_ID" \
  --region "$AWS_REGION" 2>/dev/null || true


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
  --region "$AWS_REGION" 2>/dev/null || true

aws s3api delete-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$AWS_REGION" 2>/dev/null || true


rm -f stack_outputs.env
rm -f uploader-lt-data.json
rm -f viewer-lt-data.json
rm -f user-data-uploader.sh
rm -f user-data-viewer.sh
rm -f uploader-policy.json
rm -f viewer-policy.json
rm -f trust-policy.json
rm -f uploader_instance_id.txt
rm -f viewer_instance_id.txt

echo ""
echo "Cleanup complete."

