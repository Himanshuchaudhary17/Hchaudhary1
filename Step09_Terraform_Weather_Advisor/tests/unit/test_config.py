import pytest

from stack.config import ConfigError, Settings


def test_settings_loads_all_required_values(
    env_values,
    tmp_path,
):
    settings = Settings.from_values(
        env_values,
        base_dir=tmp_path,
    )

    assert settings.region == "us-east-2"
    assert settings.app_sg_id == "sg-12345678"

    assert settings.weather.listener_port == 8080
    assert settings.advisor.listener_port == 8081

    assert settings.db_name == "weather"
    assert settings.db_user == "weatherapp"
    assert settings.db_port == 5432

    assert settings.cache_seconds == 600

    assert (
        settings.gemini_model
        == "gemini-3.1-flash-lite"
    )

    assert settings.key_cache_seconds == 60


def test_settings_builds_app_paths(
    env_values,
    tmp_path,
):
    settings = Settings.from_values(
        env_values,
        base_dir=tmp_path,
    )

    assert (
        settings.weather.app_dir
        == tmp_path / "weather-app"
    )

    assert (
        settings.advisor.app_dir
        == tmp_path / "advisor-app"
    )


def test_settings_reports_missing_keys(
    env_values,
    tmp_path,
):
    del env_values["AMI_ID"]

    with pytest.raises(
        ConfigError
    ) as exc:
        Settings.from_values(
            env_values,
            base_dir=tmp_path,
        )

    assert "AMI_ID" in str(
        exc.value
    )


def test_tier_lookup(
    env_values,
    tmp_path,
):
    settings = Settings.from_values(
        env_values,
        base_dir=tmp_path,
    )

    assert (
        settings.tier("weather")
        is settings.weather
    )

    assert (
        settings.tier("advisor")
        is settings.advisor
    )
