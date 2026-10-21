import pytest

from stack.config import ConfigError, Settings


def test_settings_loads_all_required_values(env_values, tmp_path):
    settings = Settings.from_values(env_values, base_dir=tmp_path)

    assert settings.region == "us-east-2"
    assert settings.bucket_name == "test-lab-bucket"
    assert settings.uploader.listener_port == 8080
    assert settings.viewer.listener_port == 8081
    assert settings.recovery_slo_seconds == 180


def test_settings_builds_app_paths(env_values, tmp_path):
    settings = Settings.from_values(env_values, base_dir=tmp_path)

    assert settings.uploader.app_dir == tmp_path / "uploader-app"
    assert settings.viewer.app_dir == tmp_path / "viewer-app"


def test_settings_reports_missing_keys(env_values, tmp_path):
    del env_values["AMI_ID"]

    with pytest.raises(ConfigError) as exc:
        Settings.from_values(env_values, base_dir=tmp_path)

    assert "AMI_ID" in str(exc.value)


def test_tier_lookup(env_values, tmp_path):
    settings = Settings.from_values(env_values, base_dir=tmp_path)

    assert settings.tier("uploader") is settings.uploader
    assert settings.tier("viewer") is settings.viewer
