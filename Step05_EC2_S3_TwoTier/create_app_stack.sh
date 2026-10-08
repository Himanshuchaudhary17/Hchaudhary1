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

echo "== Launching EC2 instances =="

launch_instance() {
  local TYPE="$1"
  local TEMPLATE="$2"
  local ID_FILE="${TYPE}_instance_id.txt"
  local ID=""
  local STATE=""

  if [[ -f "$ID_FILE" ]]; then
    ID=$(cat "$ID_FILE")
    STATE=$(aws ec2 describe-instances \
      --instance-ids "$ID" \
      --region "$AWS_REGION" \
      --query "Reservations[0].Instances[0].State.Name" \
      --output text 2>/dev/null || true)
  fi

  if [[ "$STATE" == "running" || "$STATE" == "pending" ]]; then
    echo "$TYPE already running: $ID"
  else
    ID=$(aws ec2 run-instances \
      --launch-template "LaunchTemplateName=$TEMPLATE,Version=\$Latest" \
      --count 1 \
      --region "$AWS_REGION" \
      --query "Instances[0].InstanceId" \
      --output text)

    echo "$ID" > "$ID_FILE"
    echo "Launched $TYPE: $ID"
  fi
}

launch_instance uploader "$UPLOADER_LT_NAME"
launch_instance viewer "$VIEWER_LT_NAME"

echo "== Waiting for EC2 instances =="

aws ec2 wait instance-running \
  --instance-ids "$(cat uploader_instance_id.txt)" \
                 "$(cat viewer_instance_id.txt)" \
  --region "$AWS_REGION"

echo "== EC2 Instance Details =="

aws ec2 describe-instances \
  --instance-ids "$(cat uploader_instance_id.txt)" \
                 "$(cat viewer_instance_id.txt)" \
  --query "Reservations[*].Instances[*].[Tags[?Key=='Name'].Value|[0],InstanceId,PublicIpAddress,State.Name]" \
  --output table \
  --region "$AWS_REGION"

echo "Wait 60-90 seconds for applications to install."
