"""User-data and EC2 launch templates for the Weather Advisor stack."""

from __future__ import annotations

import base64
import logging

from botocore.exceptions import ClientError

from .clients import AwsClients
from .config import Settings, Tier
from .util import error_code


log = logging.getLogger("stack")


def _b64_file(path) -> str:
    """Return a file encoded as base64 text."""
    return base64.b64encode(
        path.read_bytes()
    ).decode()


def build_user_data(
    settings: Settings,
    tier: Tier,
    *,
    db_host: str | None = None,
    alb_dns_name: str | None = None,
) -> str:
    """Build EC2 user-data for weather or advisor."""

    app_js = _b64_file(
        tier.app_dir / "app.js"
    )

    package_json = _b64_file(
        tier.app_dir / "package.json"
    )

    extra_setup = ""
    environment_lines = []

    if tier.name == "weather":
        if not db_host:
            raise ValueError(
                "db_host is required for the weather tier"
            )

        environment_lines = [
            f'Environment="NWS_USER_AGENT=(Weather Advisor, {settings.contact_email})"',
            f"Environment=DB_HOST={db_host}",
            f"Environment=DB_NAME={settings.db_name}",
            f"Environment=DB_USER={settings.db_user}",
            f"Environment=DB_PASSWORD_PARAM={settings.db_password_param}",
            f"Environment=CACHE_SECONDS={settings.cache_seconds}",
        ]

        extra_setup = """
dnf install -y postgresql15
curl -sS -o /opt/app/rds-ca.pem \
https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
"""

    elif tier.name == "advisor":
        if not alb_dns_name:
            raise ValueError(
                "alb_dns_name is required for the advisor tier"
            )

        environment_lines = [
            (
                "Environment=WEATHER_URL="
                f"http://{alb_dns_name}:{settings.weather.listener_port}"
            ),
            f"Environment=GEMINI_KEY_PARAM={settings.gemini_param_name}",
            f"Environment=GEMINI_MODEL={settings.gemini_model}",
            f"Environment=KEY_CACHE_SECONDS={settings.key_cache_seconds}",
        ]

    else:
        raise ValueError(
            f"Unknown tier: {tier.name}"
        )

    extra_environment = "\n".join(
        environment_lines
    )

    return f"""#!/bin/bash
dnf update -y
dnf install -y nodejs

mkdir -p /opt/app

{extra_setup}

echo "{app_js}" | base64 -d > /opt/app/app.js
echo "{package_json}" | base64 -d > /opt/app/package.json

cd /opt/app
npm install --omit=dev

cat > /etc/systemd/system/{tier.service_name}.service << 'SERVICE'
[Unit]
Description={tier.name.capitalize()} App
After=network.target

[Service]
Environment=PORT={settings.app_port}
Environment=AWS_REGION={settings.region}
{extra_environment}
WorkingDirectory=/opt/app
ExecStart=/usr/bin/node /opt/app/app.js
Restart=always
User=ec2-user

[Install]
WantedBy=multi-user.target
SERVICE

chown -R ec2-user:ec2-user /opt/app

systemctl daemon-reload
systemctl enable {tier.service_name}.service
systemctl start {tier.service_name}.service
"""


def launch_template_data(
    settings: Settings,
    tier: Tier,
    *,
    db_host: str | None = None,
    alb_dns_name: str | None = None,
) -> dict:
    """Build launch template data."""

    user_data = build_user_data(
        settings,
        tier,
        db_host=db_host,
        alb_dns_name=alb_dns_name,
    )

    return {
        "ImageId": settings.ami_id,
        "InstanceType": settings.instance_type,
        "KeyName": settings.key_name,
        "SecurityGroupIds": [
            settings.app_sg_id
        ],
        "IamInstanceProfile": {
            "Name": tier.profile_name
        },
        "UserData": base64.b64encode(
            user_data.encode()
        ).decode(),
        "TagSpecifications": [
            {
                "ResourceType": "instance",
                "Tags": [
                    {
                        "Key": "Name",
                        "Value": f"{tier.name}-app",
                    }
                ],
            }
        ],
    }


def launch_template_exists(
    aws: AwsClients,
    tier: Tier,
) -> bool:
    """Return True when the launch template exists."""

    try:
        aws.ec2.describe_launch_templates(
            LaunchTemplateNames=[
                tier.lt_name
            ]
        )
        return True

    except ClientError as err:
        if (
            error_code(err)
            != "InvalidLaunchTemplateName.NotFoundException"
        ):
            raise

        return False


def ensure_launch_template(
    aws: AwsClients,
    settings: Settings,
    tier: Tier,
    *,
    db_host: str | None = None,
    alb_dns_name: str | None = None,
) -> int:
    """Create or publish a new launch-template version."""

    data = launch_template_data(
        settings,
        tier,
        db_host=db_host,
        alb_dns_name=alb_dns_name,
    )

    if not launch_template_exists(
        aws,
        tier,
    ):
        aws.ec2.create_launch_template(
            LaunchTemplateName=tier.lt_name,
            LaunchTemplateData=data,
        )

        log.info(
            "Created launch template %s",
            tier.lt_name,
        )

        return 1

    response = (
        aws.ec2.create_launch_template_version(
            LaunchTemplateName=tier.lt_name,
            SourceVersion="$Latest",
            LaunchTemplateData=data,
        )
    )

    version = response[
        "LaunchTemplateVersion"
    ]["VersionNumber"]

    log.info(
        "Template %s exists, published version %s",
        tier.lt_name,
        version,
    )

    return version


def delete_launch_template(
    aws: AwsClients,
    tier: Tier,
) -> None:
    """Delete a launch template if it exists."""

    if launch_template_exists(
        aws,
        tier,
    ):
        aws.ec2.delete_launch_template(
            LaunchTemplateName=tier.lt_name
        )

        log.info(
            "Deleted launch template %s",
            tier.lt_name,
        )
