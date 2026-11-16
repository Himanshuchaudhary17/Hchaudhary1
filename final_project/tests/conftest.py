"""Shared pytest fixtures for the Weather Advisor final project."""

from __future__ import annotations

import json

import pytest
from moto import mock_aws

from stack.clients import AwsClients
from stack.config import Settings


@pytest.fixture
def fake_settings(
    tmp_path,
) -> Settings:
    """Return isolated final-project settings for unit tests."""

    weather_dir = (
        tmp_path / "weather-app"
    )

    advisor_dir = (
        tmp_path / "advisor-app"
    )

    weather_dir.mkdir()
    advisor_dir.mkdir()

    for directory in (
        weather_dir,
        advisor_dir,
    ):
        (
            directory / "app.js"
        ).write_text(
            "console.log('test app');\n"
        )

        (
            directory / "package.json"
        ).write_text(
            json.dumps(
                {
                    "name": "test-app",
                    "version": "1.0.0",
                    "dependencies": {},
                }
            )
        )

    values = {
        "AWS_REGION":
            "us-east-2",

        "AMI_ID":
            "ami-1234567890abcdef0",

        "KEY_NAME":
            "test-key",

        "INSTANCE_TYPE":
            "t3.micro",

        "APP_SECURITY_GROUP_ID":
            "sg-12345678",

        "AZ_A":
            "us-east-2a",

        "AZ_B":
            "us-east-2b",

        "APP_PORT":
            "3000",

        "WEATHER_ROLE_NAME":
            "test-weather-role",

        "WEATHER_PROFILE_NAME":
            "test-weather-profile",

        "WEATHER_LT_NAME":
            "test-weather-lt",

        "WEATHER_TG_NAME":
            "test-weather-tg",

        "WEATHER_ASG_NAME":
            "test-weather-asg",

        "WEATHER_LISTENER_PORT":
            "8081",

        "ADVISOR_ROLE_NAME":
            "test-advisor-role",

        "ADVISOR_PROFILE_NAME":
            "test-advisor-profile",

        "ADVISOR_LT_NAME":
            "test-advisor-lt",

        "ADVISOR_TG_NAME":
            "test-advisor-tg",

        "ADVISOR_ASG_NAME":
            "test-advisor-asg",

        "ADVISOR_LISTENER_PORT":
            "8080",

        "ALB_NAME":
            "test-weather-advisor-alb",

        "ALB_SG_NAME":
            "test-weather-advisor-alb-sg",

        "WEATHER_TABLE_NAME":
            "test-weather-cache",

        "ADVISOR_TABLE_NAME":
            "test-advisor-state",

        "CACHE_SECONDS":
            "600",

        "STALE_CACHE_SECONDS":
            "21600",

        "SNS_TOPIC_NAME":
            "test-weather-reports",

        "GEMINI_PARAM_NAME":
            "/itmo-544/final/gemini-api-key",

        "GEMINI_MODEL":
            "gemini-3.1-flash-lite",

        "KEY_CACHE_SECONDS":
            "60",

        "CONTACT_EMAIL":
            "student@example.com",
    }

    settings = Settings.from_values(
        values,
        base_dir=tmp_path,
    )

    return settings


@pytest.fixture
def moto_aws():
    """Return mocked AWS clients."""

    with mock_aws():
        yield AwsClients.create(
            "us-east-2"
        )
