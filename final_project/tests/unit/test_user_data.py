"""Unit tests for compact EC2 user-data."""

from __future__ import annotations

import base64
import io
import re
import tarfile

from stack.compute import (
    build_user_data,
    launch_template_data,
)


TEST_SNS_ARN = (
    "arn:aws:sns:us-east-2:"
    "123456789012:"
    "test-weather-reports"
)


def extract_archive(
    user_data: str,
) -> dict[str, bytes]:
    """Decode the compressed application archive from user-data."""

    match = re.search(
        r'PAYLOAD = """(.*?)"""',
        user_data,
        re.DOTALL,
    )

    assert match is not None

    compressed = (
        base64.b85decode(
            match.group(1)
            .encode("ascii")
        )
    )

    files: dict[str, bytes] = {}

    with tarfile.open(
        fileobj=io.BytesIO(
            compressed
        ),
        mode="r:xz",
    ) as archive:
        for member in (
            archive.getmembers()
        ):
            if not member.isfile():
                continue

            extracted = (
                archive.extractfile(
                    member
                )
            )

            assert (
                extracted
                is not None
            )

            files[
                member.name
            ] = (
                extracted.read()
            )

    return files


def service_text(
    user_data: str,
    service_name: str,
) -> str:
    """Return the embedded systemd unit as text."""

    files = extract_archive(
        user_data
    )

    path = (
        "etc/systemd/system/"
        f"{service_name}.service"
    )

    assert path in files

    return (
        files[path]
        .decode()
    )


def test_weather_user_data_contains_required_settings(
    fake_settings,
):
    data = build_user_data(
        fake_settings,
        fake_settings.weather,
    )

    service = service_text(
        data,
        "weather",
    )

    assert (
        "AWS_REGION=us-east-2"
        in service
    )

    assert (
        "WEATHER_TABLE="
        "test-weather-cache"
        in service
    )

    assert (
        "CACHE_SECONDS=600"
        in service
    )

    assert (
        "STALE_CACHE_SECONDS=21600"
        in service
    )


def test_advisor_user_data_contains_required_settings(
    fake_settings,
):
    data = build_user_data(
        fake_settings,
        fake_settings.advisor,
        alb_dns_name=
            "test-alb.example.com",
        sns_topic_arn=
            TEST_SNS_ARN,
    )

    service = service_text(
        data,
        "advisor",
    )

    assert (
        "WEATHER_URL="
        "http://test-alb.example.com:8081"
        in service
    )

    assert (
        "ADVISOR_TABLE="
        "test-advisor-state"
        in service
    )

    assert (
        f"SNS_TOPIC_ARN={TEST_SNS_ARN}"
        in service
    )

    assert (
        "GEMINI_KEY_PARAM="
        "/itmo-544/final/gemini-api-key"
        in service
    )

    assert (
        "GEMINI_MODEL="
        "gemini-3.1-flash-lite"
        in service
    )

    assert (
        "REPORT_CACHE_SECONDS=600"
        in service
    )


def test_user_data_uses_python_not_bash(
    fake_settings,
):
    weather = build_user_data(
        fake_settings,
        fake_settings.weather,
    )

    advisor = build_user_data(
        fake_settings,
        fake_settings.advisor,
        alb_dns_name=
            "test-alb.example.com",
        sns_topic_arn=
            TEST_SNS_ARN,
    )

    assert weather.startswith(
        "#!/usr/bin/python3"
    )

    assert advisor.startswith(
        "#!/usr/bin/python3"
    )

    assert (
        "#!/bin/bash"
        not in weather
    )

    assert (
        "#!/bin/bash"
        not in advisor
    )


def test_weather_archive_contains_application_files(
    fake_settings,
):
    data = build_user_data(
        fake_settings,
        fake_settings.weather,
    )

    files = extract_archive(
        data
    )

    assert (
        "opt/app/app.js"
        in files
    )

    assert (
        "opt/app/package.json"
        in files
    )

    assert (
        "etc/systemd/system/"
        "weather.service"
        in files
    )


def test_advisor_archive_contains_application_files(
    fake_settings,
):
    data = build_user_data(
        fake_settings,
        fake_settings.advisor,
        alb_dns_name=
            "test-alb.example.com",
        sns_topic_arn=
            TEST_SNS_ARN,
    )

    files = extract_archive(
        data
    )

    assert (
        "opt/app/app.js"
        in files
    )

    assert (
        "opt/app/package.json"
        in files
    )

    assert (
        "etc/systemd/system/"
        "advisor.service"
        in files
    )


def test_user_data_boot_script_extracts_archive(
    fake_settings,
):
    data = build_user_data(
        fake_settings,
        fake_settings.weather,
    )

    assert (
        "b85decode"
        in data
    )

    assert (
        "tarfile.open"
        in data
    )

    assert (
        '"npm",'
        in data
    )

    assert (
        '"systemctl",'
        in data
    )


def test_services_use_node_app(
    fake_settings,
):
    weather = build_user_data(
        fake_settings,
        fake_settings.weather,
    )

    advisor = build_user_data(
        fake_settings,
        fake_settings.advisor,
        alb_dns_name=
            "test-alb.example.com",
        sns_topic_arn=
            TEST_SNS_ARN,
    )

    weather_service = (
        service_text(
            weather,
            "weather",
        )
    )

    advisor_service = (
        service_text(
            advisor,
            "advisor",
        )
    )

    assert (
        "ExecStart=/usr/bin/node "
        "/opt/app/app.js"
        in weather_service
    )

    assert (
        "ExecStart=/usr/bin/node "
        "/opt/app/app.js"
        in advisor_service
    )


def test_launch_template_data_uses_expected_settings(
    fake_settings,
):
    data = launch_template_data(
        fake_settings,
        fake_settings.weather,
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

    assert (
        data["SecurityGroupIds"]
        == [
            fake_settings.app_sg_id
        ]
    )

    assert (
        data[
            "IamInstanceProfile"
        ][
            "Name"
        ]
        == (
            fake_settings
            .weather
            .profile_name
        )
    )

    decoded = (
        base64.b64decode(
            data["UserData"]
        )
        .decode()
    )

    assert (
        decoded.startswith(
            "#!/usr/bin/python3"
        )
    )


def test_user_data_stays_under_16kb(
    fake_settings,
):
    weather = build_user_data(
        fake_settings,
        fake_settings.weather,
    )

    advisor = build_user_data(
        fake_settings,
        fake_settings.advisor,
        alb_dns_name=
            "test-alb.example.com",
        sns_topic_arn=
            TEST_SNS_ARN,
    )

    assert (
        len(
            weather.encode()
        )
        <= 16384
    )

    assert (
        len(
            advisor.encode()
        )
        <= 16384
    )
