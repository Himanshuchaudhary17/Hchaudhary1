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
        "APP_SECURITY_GROUP_ID": "sg-12345678",

        "AZ_A": "us-east-2a",
        "AZ_B": "us-east-2b",

        "WEATHER_ROLE_NAME": "weather-role",
        "WEATHER_PROFILE_NAME": "weather-profile",
        "WEATHER_LT_NAME": "weather-lt",
        "WEATHER_TG_NAME": "weather-tg",
        "WEATHER_ASG_NAME": "weather-asg",
        "WEATHER_LISTENER_PORT": "8080",

        "ADVISOR_ROLE_NAME": "advisor-role",
        "ADVISOR_PROFILE_NAME": "advisor-profile",
        "ADVISOR_LT_NAME": "advisor-lt",
        "ADVISOR_TG_NAME": "advisor-tg",
        "ADVISOR_ASG_NAME": "advisor-asg",
        "ADVISOR_LISTENER_PORT": "8081",

        "ALB_NAME": "test-weather-alb",
        "ALB_SG_NAME": "test-weather-alb-sg",

        "DB_INSTANCE_ID": "test-weather-db",
        "DB_NAME": "weather",
        "DB_USER": "weatherapp",
        "DB_SG_NAME": "test-weather-db-sg",
        "DB_SUBNET_GROUP_NAME": "test-weather-db-subnets",
        "DB_PASSWORD_PARAM": "/itmo-444-544/db-password",
        "CACHE_SECONDS": "600",

        "GEMINI_PARAM_NAME": "/itmo-444-544/gemini-api-key",
        "GEMINI_MODEL": "gemini-3.1-flash-lite",
        "KEY_CACHE_SECONDS": "60",

        "CONTACT_EMAIL": "student@example.edu",
    }


@pytest.fixture
def fake_settings(
    tmp_path: Path,
    env_values,
):
    for name in (
        "weather-app",
        "advisor-app",
    ):
        app_dir = tmp_path / name
        app_dir.mkdir()

        (app_dir / "app.js").write_text(
            "console.log('test');\n"
        )

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

        session = boto3.session.Session(
            region_name=region
        )

        ec2 = session.client("ec2")

        clients = AwsClients(
            s3=session.client("s3"),
            iam=session.client("iam"),
            ec2=ec2,
            elbv2=session.client("elbv2"),
            autoscaling=session.client(
                "autoscaling"
            ),
            rds=session.client("rds"),
            ssm=session.client("ssm"),
            sts=session.client("sts"),
        )

        yield clients


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def settings():
    return Settings.from_file(
        ROOT / ".env"
    )


@pytest.fixture(scope="session")
def aws(settings):
    return AwsClients.create(
        settings.region
    )


@pytest.fixture(scope="session")
def outputs():
    try:
        return StackOutputs.load(
            ROOT
        )

    except FileNotFoundError:
        pytest.skip(
            "stack_outputs.json not found. "
            "Run python create_weather_stack.py first."
        )
