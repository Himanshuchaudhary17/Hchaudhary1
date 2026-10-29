import base64

from stack.compute import (
    build_user_data,
    launch_template_data,
)


def test_weather_user_data_contains_db_and_region(
    fake_settings,
):
    data = build_user_data(
        fake_settings,
        fake_settings.weather,
        db_host="test-db.example.com",
    )

    assert "AWS_REGION=us-east-2" in data
    assert "DB_HOST=test-db.example.com" in data
    assert "DB_NAME=weather" in data
    assert "DB_USER=weatherapp" in data

    assert (
        "DB_PASSWORD_PARAM="
        "/itmo-444-544/db-password"
    ) in data

    assert "CACHE_SECONDS=600" in data


def test_advisor_user_data_contains_weather_and_gemini_settings(
    fake_settings,
):
    data = build_user_data(
        fake_settings,
        fake_settings.advisor,
        alb_dns_name="test-alb.example.com",
    )

    assert (
        "WEATHER_URL="
        "http://test-alb.example.com:8080"
    ) in data

    assert (
        "GEMINI_KEY_PARAM="
        "/itmo-444-544/gemini-api-key"
    ) in data

    assert (
        "GEMINI_MODEL="
        "gemini-3.1-flash-lite"
    ) in data

    assert "KEY_CACHE_SECONDS=60" in data


def test_weather_user_data_contains_app_files(
    fake_settings,
):
    data = build_user_data(
        fake_settings,
        fake_settings.weather,
        db_host="test-db.example.com",
    )

    app_js_b64 = base64.b64encode(
        (
            fake_settings.weather.app_dir
            / "app.js"
        ).read_bytes()
    ).decode()

    package_b64 = base64.b64encode(
        (
            fake_settings.weather.app_dir
            / "package.json"
        ).read_bytes()
    ).decode()

    assert app_js_b64 in data
    assert package_b64 in data


def test_user_data_starts_correct_services(
    fake_settings,
):
    weather_data = build_user_data(
        fake_settings,
        fake_settings.weather,
        db_host="test-db.example.com",
    )

    advisor_data = build_user_data(
        fake_settings,
        fake_settings.advisor,
        alb_dns_name="test-alb.example.com",
    )

    assert (
        "systemctl enable weather.service"
        in weather_data
    )
    assert (
        "systemctl start weather.service"
        in weather_data
    )

    assert (
        "systemctl enable advisor.service"
        in advisor_data
    )
    assert (
        "systemctl start advisor.service"
        in advisor_data
    )


def test_launch_template_data_uses_expected_weather_settings(
    fake_settings,
):
    data = launch_template_data(
        fake_settings,
        fake_settings.weather,
        db_host="test-db.example.com",
    )

    assert (
        data["ImageId"]
        == fake_settings.ami_id
    )

    assert (
        data["InstanceType"]
        == fake_settings.instance_type
    )

    assert (
        data["KeyName"]
        == fake_settings.key_name
    )

    assert data["SecurityGroupIds"] == [
        fake_settings.app_sg_id
    ]

    assert data["IamInstanceProfile"] == {
        "Name":
            fake_settings.weather.profile_name
    }

    assert data["UserData"]


def test_user_data_stays_under_16kb(
    fake_settings,
):
    weather_data = build_user_data(
        fake_settings,
        fake_settings.weather,
        db_host="test-db.example.com",
    )

    advisor_data = build_user_data(
        fake_settings,
        fake_settings.advisor,
        alb_dns_name="test-alb.example.com",
    )

    assert (
        len(weather_data.encode())
        < 16 * 1024
    )

    assert (
        len(advisor_data.encode())
        < 16 * 1024
    )
