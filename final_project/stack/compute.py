"""EC2 launch templates for the Weather Advisor final project."""

from __future__ import annotations

import base64
import io
import logging
import tarfile

from botocore.exceptions import ClientError

from .clients import AwsClients
from .config import Settings, Tier
from .util import error_code


log = logging.getLogger("stack")


def _archive_b85(
    tier: Tier,
    service_text: str,
) -> str:
    """Build a compressed Base85 application archive."""

    files = {
        "opt/app/app.js":
            (tier.app_dir / "app.js").read_bytes(),

        "opt/app/package.json":
            (tier.app_dir / "package.json").read_bytes(),

        (
            "etc/systemd/system/"
            f"{tier.service_name}.service"
        ):
            service_text.encode(),
    }

    buffer = io.BytesIO()

    with tarfile.open(
        fileobj=buffer,
        mode="w:gz",
        compresslevel=9,
    ) as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(
                name=name
            )

            info.size = len(
                content
            )

            info.mtime = 0
            info.mode = 0o644

            archive.addfile(
                info,
                io.BytesIO(
                    content
                ),
            )

    return (
        base64.b85encode(
            buffer.getvalue()
        )
        .decode("ascii")
    )


def build_user_data(
    settings: Settings,
    tier: Tier,
    *,
    alb_dns_name: str | None = None,
    sns_topic_arn: str | None = None,
) -> str:
    """Build compact Python EC2 user-data."""

    environment: dict[str, str] = {
        "PORT": str(
            settings.app_port
        ),

        "AWS_REGION":
            settings.region,
    }

    if tier.name == "weather":
        environment.update(
            {
                "NWS_USER_AGENT": (
                    "(Weather Advisor Final Project, "
                    f"{settings.contact_email})"
                ),

                "WEATHER_TABLE":
                    settings.weather_table_name,

                "CACHE_SECONDS": str(
                    settings.cache_seconds
                ),

                "STALE_CACHE_SECONDS": str(
                    settings.stale_cache_seconds
                ),
            }
        )

    elif tier.name == "advisor":
        if not alb_dns_name:
            raise ValueError(
                "alb_dns_name is required "
                "for the advisor tier"
            )

        if not sns_topic_arn:
            raise ValueError(
                "sns_topic_arn is required "
                "for the advisor tier"
            )

        environment.update(
            {
                "WEATHER_URL": (
                    f"http://{alb_dns_name}:"
                    f"{settings.weather.listener_port}"
                ),

                "ADVISOR_TABLE":
                    settings.advisor_table_name,

                "SNS_TOPIC_ARN":
                    sns_topic_arn,

                "GEMINI_KEY_PARAM":
                    settings.gemini_param_name,

                "GEMINI_MODEL":
                    settings.gemini_model,

                "KEY_CACHE_SECONDS": str(
                    settings.key_cache_seconds
                ),

                "REPORT_CACHE_SECONDS":
                    "600",
            }
        )

    else:
        raise ValueError(
            f"Unknown tier: {tier.name}"
        )

    env_lines = "\n".join(
        f'Environment="{key}={value}"'
        for key, value
        in environment.items()
    )

    service_text = f"""[Unit]
Description={tier.name.capitalize()} Weather Advisor App
After=network-online.target
Wants=network-online.target

[Service]
{env_lines}
WorkingDirectory=/opt/app
ExecStart=/usr/bin/node /opt/app/app.js
Restart=always
RestartSec=3
User=ec2-user

[Install]
WantedBy=multi-user.target
"""

    payload = _archive_b85(
        tier,
        service_text,
    )

    python_boot = f'''#!/usr/bin/python3
import base64
import io
import pathlib
import subprocess
import tarfile

PAYLOAD = """{payload}"""


def run(args, cwd=None):
    subprocess.run(
        args,
        cwd=cwd,
        check=True,
    )


def main():
    run([
        "dnf",
        "install",
        "-y",
        "nodejs",
    ])

    pathlib.Path(
        "/opt/app"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    data = base64.b85decode(
        PAYLOAD.encode("ascii")
    )

    with tarfile.open(
        fileobj=io.BytesIO(data),
        mode="r:gz",
    ) as archive:
        archive.extractall("/")

    run([
        "npm",
        "install",
        "--omit=dev",
    ], cwd="/opt/app")

    run([
        "chown",
        "-R",
        "ec2-user:ec2-user",
        "/opt/app",
    ])

    run([
        "systemctl",
        "daemon-reload",
    ])

    run([
        "systemctl",
        "enable",
        "{tier.service_name}.service",
    ])

    run([
        "systemctl",
        "restart",
        "{tier.service_name}.service",
    ])


if __name__ == "__main__":
    main()
'''

    return python_boot


def launch_template_data(
    settings: Settings,
    tier: Tier,
    *,
    alb_dns_name: str | None = None,
    sns_topic_arn: str | None = None,
) -> dict:
    """Build EC2 launch-template data."""

    user_data = build_user_data(
        settings,
        tier,
        alb_dns_name=alb_dns_name,
        sns_topic_arn=sns_topic_arn,
    )

    return {
        "ImageId":
            settings.ami_id,

        "InstanceType":
            settings.instance_type,

        "KeyName":
            settings.key_name,

        "SecurityGroupIds": [
            settings.app_sg_id
        ],

        "IamInstanceProfile": {
            "Name":
                tier.profile_name
        },

        "UserData":
            base64.b64encode(
                user_data.encode()
            ).decode(),

        "TagSpecifications": [
            {
                "ResourceType":
                    "instance",

                "Tags": [
                    {
                        "Key":
                            "Name",

                        "Value":
                            f"{tier.name}-app",
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
            !=
            "InvalidLaunchTemplateName.NotFoundException"
        ):
            raise

        return False


def ensure_launch_template(
    aws: AwsClients,
    settings: Settings,
    tier: Tier,
    *,
    alb_dns_name: str | None = None,
    sns_topic_arn: str | None = None,
) -> int:
    """Create or publish a launch-template version."""

    data = launch_template_data(
        settings,
        tier,
        alb_dns_name=alb_dns_name,
        sns_topic_arn=sns_topic_arn,
    )

    if not launch_template_exists(
        aws,
        tier,
    ):
        response = (
            aws.ec2
            .create_launch_template(
                LaunchTemplateName=
                    tier.lt_name,

                LaunchTemplateData=
                    data,
            )
        )

        version = int(
            response[
                "LaunchTemplate"
            ][
                "LatestVersionNumber"
            ]
        )

        log.info(
            "Created launch template %s "
            "version %s",
            tier.lt_name,
            version,
        )

        return version

    response = (
        aws.ec2
        .create_launch_template_version(
            LaunchTemplateName=
                tier.lt_name,

            SourceVersion=
                "$Latest",

            LaunchTemplateData=
                data,
        )
    )

    version = int(
        response[
            "LaunchTemplateVersion"
        ][
            "VersionNumber"
        ]
    )

    log.info(
        "Published launch template %s "
        "version %s",
        tier.lt_name,
        version,
    )

    return version


def delete_launch_template(
    aws: AwsClients,
    tier: Tier,
) -> None:
    """Delete a launch template when present."""

    if not launch_template_exists(
        aws,
        tier,
    ):
        log.info(
            "Launch template %s already absent.",
            tier.lt_name,
        )

        return

    aws.ec2.delete_launch_template(
        LaunchTemplateName=
            tier.lt_name
    )

    log.info(
        "Deleted launch template %s",
        tier.lt_name,
    )
