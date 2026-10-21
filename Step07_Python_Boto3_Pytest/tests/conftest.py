from __future__ import annotations

from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from stack.clients import AwsClients
from stack.config import Settings
from stack.outputs import StackOutputs


@pytest.fixture
def env_values():
    return {
        "AWS_REGION": "us-east-2",
        "AMI_ID": "ami-1234567890abcdef0",
        "KEY_NAME": "test-key",
        "INSTANCE_TYPE": "t3.micro",
        "BUCKET_NAME": "test-lab-bucket",
        "APP_SECURITY_GROUP_ID": "sg-12345678",

        "UPLOADER_ROLE_NAME": "uploader-role",
        "UPLOADER_PROFILE_NAME": "uploader-profile",
        "UPLOADER_LT_NAME": "uploader-lt",
        "UPLOADER_TG_NAME": "uploader-tg",
        "UPLOADER_ASG_NAME": "uploader-asg",
        "UPLOADER_LISTENER_PORT": "8080",

        "VIEWER_ROLE_NAME": "viewer-role",
        "VIEWER_PROFILE_NAME": "viewer-profile",
        "VIEWER_LT_NAME": "viewer-lt",
        "VIEWER_TG_NAME": "viewer-tg",
        "VIEWER_ASG_NAME": "viewer-asg",
        "VIEWER_LISTENER_PORT": "8081",

        "ALB_NAME": "test-alb",
        "ALB_SG_NAME": "test-alb-sg",
        "AZ_A": "us-east-2a",
        "AZ_B": "us-east-2b",
        "RECOVERY_SLO_SECONDS": "180",
    }


@pytest.fixture
def fake_settings(tmp_path: Path, env_values):
    for name in ("uploader-app", "viewer-app"):
        app_dir = tmp_path / name
        app_dir.mkdir()
        (app_dir / "app.js").write_text("console.log('test');\n")
        (app_dir / "package.json").write_text(
            '{"name":"test-app","version":"1.0.0"}\n'
        )

    return Settings.from_values(
        env_values,
        base_dir=tmp_path,
    )


@pytest.fixture
def moto_aws():
    with mock_aws():
        region = "us-east-2"

        session = boto3.session.Session(region_name=region)

        ec2 = session.client("ec2")
        ec2.create_vpc(CidrBlock="10.0.0.0/16")

        image = ec2.describe_images()["Images"][0]

        clients = AwsClients(
            s3=session.client("s3"),
            iam=session.client("iam"),
            ec2=ec2,
            elbv2=session.client("elbv2"),
            autoscaling=session.client("autoscaling"),
        )

        yield clients


ROOT = Path(__file__).resolve().parent.parent


# ---- fixtures for tests that talk to your deployed stack ----

@pytest.fixture(scope="session")
def settings():
    return Settings.from_file(ROOT / ".env")


@pytest.fixture(scope="session")
def aws(settings):
    return AwsClients.create(settings.region)


@pytest.fixture(scope="session")
def outputs():
    try:
        return StackOutputs.load(ROOT)
    except FileNotFoundError:
        pytest.skip(
            "stack_outputs.json not found. Run python create_stack.py first."
        )
