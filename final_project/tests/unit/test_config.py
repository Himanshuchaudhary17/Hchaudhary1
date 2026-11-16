"""Unit tests for final-project configuration."""

from __future__ import annotations

import pytest

from stack.config import (
    ConfigError,
    Settings,
)


def test_settings_loads_required_values(
    fake_settings,
):
    assert (
        fake_settings.region
        == "us-east-2"
    )

    assert (
        fake_settings.instance_type
        == "t3.micro"
    )

    assert (
        fake_settings.weather_table_name
        == "test-weather-cache"
    )

    assert (
        fake_settings.advisor_table_name
        == "test-advisor-state"
    )

    assert (
        fake_settings.sns_topic_name
        == "test-weather-reports"
    )

    assert (
        fake_settings.gemini_model
        == "gemini-3.1-flash-lite"
    )


def test_settings_builds_app_paths(
    fake_settings,
):
    assert (
        fake_settings.weather.app_dir.name
        == "weather-app"
    )

    assert (
        fake_settings.advisor.app_dir.name
        == "advisor-app"
    )


def test_listener_ports(
    fake_settings,
):
    assert (
        fake_settings.weather.listener_port
        == 8081
    )

    assert (
        fake_settings.advisor.listener_port
        == 8080
    )


def test_tier_lookup(
    fake_settings,
):
    assert (
        fake_settings.tier("weather")
        is fake_settings.weather
    )

    assert (
        fake_settings.tier("advisor")
        is fake_settings.advisor
    )


def test_settings_reports_missing_keys(
    tmp_path,
):
    with pytest.raises(
        ConfigError,
        match="Missing keys",
    ):
        Settings.from_values(
            {
                "AWS_REGION":
                    "us-east-2",
            },
            base_dir=tmp_path,
        )
