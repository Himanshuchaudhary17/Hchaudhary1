#!/bin/bash
set -e
cd "$(dirname "$0")"

set -a
source .env
set +a

echo "== Checking S3 bucket =="

if aws s3api head-bucket --bucket "$BUCKET_NAME" --region "$AWS_REGION" 2>/dev/null; then
  echo "Bucket already exists."
else
  aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$AWS_REGION" \
    --create-bucket-configuration "LocationConstraint=$AWS_REGION"
fi

echo "== Configuring IAM roles =="

setup_role() {
  local ROLE="$1"
  local PROFILE="$2"
  local POLICY_NAME="$3"
  local POLICY_FILE="$4"

  if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
    aws iam create-role \
      --role-name "$ROLE" \
      --assume-role-policy-document file://trust-policy.json
  fi

  aws iam put-role-policy \
    --role-name "$ROLE" \
    --policy-name "$POLICY_NAME" \
    --policy-document "file://$POLICY_FILE"

  if ! aws iam get-instance-profile \
    --instance-profile-name "$PROFILE" >/dev/null 2>&1; then
    aws iam create-instance-profile \
      --instance-profile-name "$PROFILE"
  fi

  if ! aws iam get-instance-profile \
    --instance-profile-name "$PROFILE" \
    --query "InstanceProfile.Roles[?RoleName=='$ROLE'].RoleName" \
    --output text | grep -q "$ROLE"; then
    aws iam add-role-to-instance-profile \
      --instance-profile-name "$PROFILE" \
      --role-name "$ROLE"
  fi
}

setup_role "$UPLOADER_ROLE_NAME" "$UPLOADER_PROFILE_NAME" \
  "uploader-put-only" uploader-policy.json

setup_role "$VIEWER_ROLE_NAME" "$VIEWER_PROFILE_NAME" \
  "viewer-read-only" viewer-policy.json

echo "Waiting for IAM propagation..."
sleep 15

echo "== Building EC2 user-data =="

build_userdata() {
  local TYPE="$1"
  local APP_B64
  local PKG_B64

  APP_B64=$(base64 -w0 "lab03/$TYPE-app/app.js")
  PKG_B64=$(base64 -w0 "lab03/$TYPE-app/package.json")

  cat > "user-data-$TYPE.sh" <<EOF
#!/bin/bash
set -e
dnf install -y nodejs
mkdir -p /opt/app
echo "$APP_B64" | base64 -d > /opt/app/app.js
echo "$PKG_B64" | base64 -d > /opt/app/package.json
cd /opt/app
npm install --omit=dev

cat > /etc/systemd/system/$TYPE.service <<SERVICE
[Unit]
Description=$TYPE Node.js Application
After=network-online.target
Wants=network-online.target

[Service]
Environment=BUCKET_NAME=$BUCKET_NAME
Environment=AWS_REGION=$AWS_REGION
Environment=PORT=$APP_PORT
WorkingDirectory=/opt/app
ExecStart=/usr/bin/node /opt/app/app.js
Restart=always
User=ec2-user

[Install]
WantedBy=multi-user.target
SERVICE

chown -R ec2-user:ec2-user /opt/app
systemctl daemon-reload
systemctl enable $TYPE.service
systemctl start $TYPE.service
EOF
}

build_userdata uploader
build_userdata viewer

echo "== Creating EC2 launch templates =="

create_template() {
  local TYPE="$1"
  local TEMPLATE_NAME="$2"
  local PROFILE_NAME="$3"
  local USERDATA_B64

  USERDATA_B64=$(base64 -w0 "user-data-$TYPE.sh")

  cat > "$TYPE-lt-data.json" <<EOF
{
  "ImageId": "$AMI_ID",
  "InstanceType": "$INSTANCE_TYPE",
  "KeyName": "$KEY_NAME",
  "SecurityGroupIds": ["$APP_SECURITY_GROUP_ID"],
  "IamInstanceProfile": {"Name": "$PROFILE_NAME"},
  "UserData": "$USERDATA_B64",
  "TagSpecifications": [
    {
      "ResourceType": "instance",
      "Tags": [
        {"Key": "Name", "Value": "$TYPE-app"}
      ]
    }
  ]
}
EOF

  if aws ec2 describe-launch-templates \
    --launch-template-names "$TEMPLATE_NAME" \
    --region "$AWS_REGION" >/dev/null 2>&1; then

    aws ec2 create-launch-template-version \
      --launch-template-name "$TEMPLATE_NAME" \
      --launch-template-data "file://$TYPE-lt-data.json" \
      --region "$AWS_REGION" >/dev/null

    echo "Updated $TEMPLATE_NAME"
  else
    aws ec2 create-launch-template \
      --launch-template-name "$TEMPLATE_NAME" \
      --launch-template-data "file://$TYPE-lt-data.json" \
      --region "$AWS_REGION" >/dev/null

    echo "Created $TEMPLATE_NAME"
  fi
}

create_template uploader "$UPLOADER_LT_NAME" "$UPLOADER_PROFILE_NAME"
create_template viewer "$VIEWER_LT_NAME" "$VIEWER_PROFILE_NAME"


echo "== Looking up the default VPC and subnets in both AZs =="

VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region "$AWS_REGION")

SUBNET_A=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=availability-zone,Values=$AZ_A" \
  --query "Subnets[0].SubnetId" \
  --output text \
  --region "$AWS_REGION")

SUBNET_B=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=availability-zone,Values=$AZ_B" \
  --query "Subnets[0].SubnetId" \
  --output text \
  --region "$AWS_REGION")

echo "VPC: $VPC_ID"
echo "$AZ_A subnet: $SUBNET_A"
echo "$AZ_B subnet: $SUBNET_B"

echo "== ALB security group =="

ALB_SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$ALB_SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" \
  --output text \
  --region "$AWS_REGION" 2>/dev/null)

if [[ "$ALB_SECURITY_GROUP_ID" == "None" || -z "$ALB_SECURITY_GROUP_ID" ]]; then

  ALB_SECURITY_GROUP_ID=$(aws ec2 create-security-group \
    --group-name "$ALB_SG_NAME" \
    --description "Allow inbound to the ALB on the app listener ports" \
    --vpc-id "$VPC_ID" \
    --query "GroupId" \
    --output text \
    --region "$AWS_REGION")

  aws ec2 authorize-security-group-ingress \
    --group-id "$ALB_SECURITY_GROUP_ID" \
    --protocol tcp \
    --port "$UPLOADER_LISTENER_PORT" \
    --cidr 0.0.0.0/0 \
    --region "$AWS_REGION" >/dev/null

  aws ec2 authorize-security-group-ingress \
    --group-id "$ALB_SECURITY_GROUP_ID" \
    --protocol tcp \
    --port "$VIEWER_LISTENER_PORT" \
    --cidr 0.0.0.0/0 \
    --region "$AWS_REGION" >/dev/null

else
  echo "ALB security group already exists, skipping."
fi


echo "== Tightening the app security group to only accept traffic from the ALB =="

aws ec2 revoke-security-group-ingress \
  --group-id "$APP_SECURITY_GROUP_ID" \
  --protocol tcp \
  --port 3000 \
  --cidr 0.0.0.0/0 \
  --region "$AWS_REGION" >/dev/null 2>&1 || true

aws ec2 authorize-security-group-ingress \
  --group-id "$APP_SECURITY_GROUP_ID" \
  --protocol tcp \
  --port 3000 \
  --source-group "$ALB_SECURITY_GROUP_ID" \
  --region "$AWS_REGION" >/dev/null 2>&1 || true


echo "== Target groups =="

UPLOADER_TG_ARN=$(aws elbv2 describe-target-groups \
  --names "$UPLOADER_TG_NAME" \
  --region "$AWS_REGION" \
  --query "TargetGroups[0].TargetGroupArn" \
  --output text 2>/dev/null || true)

if [[ "$UPLOADER_TG_ARN" == "None" || -z "$UPLOADER_TG_ARN" ]]; then

  UPLOADER_TG_ARN=$(aws elbv2 create-target-group \
    --name "$UPLOADER_TG_NAME" \
    --protocol HTTP \
    --port 3000 \
    --vpc-id "$VPC_ID" \
    --target-type instance \
    --health-check-protocol HTTP \
    --health-check-path / \
    --health-check-interval-seconds 10 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 2 \
    --region "$AWS_REGION" \
    --query "TargetGroups[0].TargetGroupArn" \
    --output text)

else
  echo "Target group $UPLOADER_TG_NAME already exists, skipping."
fi


VIEWER_TG_ARN=$(aws elbv2 describe-target-groups \
  --names "$VIEWER_TG_NAME" \
  --region "$AWS_REGION" \
  --query "TargetGroups[0].TargetGroupArn" \
  --output text 2>/dev/null || true)

if [[ "$VIEWER_TG_ARN" == "None" || -z "$VIEWER_TG_ARN" ]]; then

  VIEWER_TG_ARN=$(aws elbv2 create-target-group \
    --name "$VIEWER_TG_NAME" \
    --protocol HTTP \
    --port 3000 \
    --vpc-id "$VPC_ID" \
    --target-type instance \
    --health-check-protocol HTTP \
    --health-check-path / \
    --health-check-interval-seconds 10 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 2 \
    --region "$AWS_REGION" \
    --query "TargetGroups[0].TargetGroupArn" \
    --output text)

else
  echo "Target group $VIEWER_TG_NAME already exists, skipping."
fi


echo "== Application Load Balancer =="

ALB_ARN=$(aws elbv2 describe-load-balancers \
  --names "$ALB_NAME" \
  --region "$AWS_REGION" \
  --query "LoadBalancers[0].LoadBalancerArn" \
  --output text 2>/dev/null || true)

if [[ "$ALB_ARN" == "None" || -z "$ALB_ARN" ]]; then

  ALB_ARN=$(aws elbv2 create-load-balancer \
    --name "$ALB_NAME" \
    --subnets "$SUBNET_A" "$SUBNET_B" \
    --security-groups "$ALB_SECURITY_GROUP_ID" \
    --scheme internet-facing \
    --type application \
    --region "$AWS_REGION" \
    --query "LoadBalancers[0].LoadBalancerArn" \
    --output text)

  echo "Waiting for the ALB to become active..."

  aws elbv2 wait load-balancer-available \
    --load-balancer-arns "$ALB_ARN" \
    --region "$AWS_REGION"

else
  echo "Load balancer $ALB_NAME already exists, skipping."
fi


echo "== Listeners =="

EXISTING_PORTS=$(aws elbv2 describe-listeners \
  --load-balancer-arn "$ALB_ARN" \
  --region "$AWS_REGION" \
  --query "Listeners[].Port" \
  --output text 2>/dev/null || true)

if ! echo "$EXISTING_PORTS" | tr '\t' '\n' | grep -qx "$UPLOADER_LISTENER_PORT"; then

  aws elbv2 create-listener \
    --load-balancer-arn "$ALB_ARN" \
    --protocol HTTP \
    --port "$UPLOADER_LISTENER_PORT" \
    --default-actions "Type=forward,TargetGroupArn=$UPLOADER_TG_ARN" \
    --region "$AWS_REGION" >/dev/null

fi


if ! echo "$EXISTING_PORTS" | tr '\t' '\n' | grep -qx "$VIEWER_LISTENER_PORT"; then

  aws elbv2 create-listener \
    --load-balancer-arn "$ALB_ARN" \
    --protocol HTTP \
    --port "$VIEWER_LISTENER_PORT" \
    --default-actions "Type=forward,TargetGroupArn=$VIEWER_TG_ARN" \
    --region "$AWS_REGION" >/dev/null

fi


ALB_DNS_NAME=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns "$ALB_ARN" \
  --query "LoadBalancers[0].DNSName" \
  --output text \
  --region "$AWS_REGION")


echo "== Auto Scaling Groups =="

EXISTING_UPLOADER_ASG=$(aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$UPLOADER_ASG_NAME" \
  --region "$AWS_REGION" \
  --query "AutoScalingGroups[0].AutoScalingGroupName" \
  --output text 2>/dev/null || true)

if [[ "$EXISTING_UPLOADER_ASG" == "None" || -z "$EXISTING_UPLOADER_ASG" ]]; then

  aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name "$UPLOADER_ASG_NAME" \
    --launch-template "LaunchTemplateName=$UPLOADER_LT_NAME,Version=\$Latest" \
    --min-size 1 \
    --max-size 1 \
    --desired-capacity 1 \
    --vpc-zone-identifier "$SUBNET_A,$SUBNET_B" \
    --target-group-arns "$UPLOADER_TG_ARN" \
    --health-check-type ELB \
    --health-check-grace-period 120 \
    --region "$AWS_REGION"

else
  echo "Auto Scaling Group $UPLOADER_ASG_NAME already exists, skipping."
fi


EXISTING_VIEWER_ASG=$(aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$VIEWER_ASG_NAME" \
  --region "$AWS_REGION" \
  --query "AutoScalingGroups[0].AutoScalingGroupName" \
  --output text 2>/dev/null || true)

if [[ "$EXISTING_VIEWER_ASG" == "None" || -z "$EXISTING_VIEWER_ASG" ]]; then

  aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name "$VIEWER_ASG_NAME" \
    --launch-template "LaunchTemplateName=$VIEWER_LT_NAME,Version=\$Latest" \
    --min-size 1 \
    --max-size 1 \
    --desired-capacity 1 \
    --vpc-zone-identifier "$SUBNET_A,$SUBNET_B" \
    --target-group-arns "$VIEWER_TG_ARN" \
    --health-check-type ELB \
    --health-check-grace-period 120 \
    --region "$AWS_REGION"

else
  echo "Auto Scaling Group $VIEWER_ASG_NAME already exists, skipping."
fi


cat > stack_outputs.env << EOF2
VPC_ID=$VPC_ID
SUBNET_A=$SUBNET_A
SUBNET_B=$SUBNET_B
ALB_SECURITY_GROUP_ID=$ALB_SECURITY_GROUP_ID
ALB_ARN=$ALB_ARN
ALB_DNS_NAME=$ALB_DNS_NAME
UPLOADER_TG_ARN=$UPLOADER_TG_ARN
VIEWER_TG_ARN=$VIEWER_TG_ARN
EOF2


echo ""
echo "Done. ALB DNS name: $ALB_DNS_NAME"
echo "Uploader: http://$ALB_DNS_NAME:$UPLOADER_LISTENER_PORT/"
echo "Viewer:   http://$ALB_DNS_NAME:$VIEWER_LISTENER_PORT/"
echo ""
echo "Give the target groups 1-2 minutes to report healthy."

