"""Integration tests against the deployed Weather Advisor application."""

from __future__ import annotations

import json
import time
from datetime import datetime
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from stack.config import Settings
from stack.outputs import StackOutputs


settings = Settings.from_file(".env")
outputs = StackOutputs.load()


WEATHER_BASE = (
    f"http://{outputs.alb_dns_name}:"
    f"{settings.weather.listener_port}"
)

ADVISOR_BASE = (
    f"http://{outputs.alb_dns_name}:"
    f"{settings.advisor.listener_port}"
)


def get_json(
    url: str,
    timeout: int = 20,
) -> dict:
    """GET one JSON endpoint."""

    with urlopen(
        url,
        timeout=timeout,
    ) as response:
        return json.loads(
            response.read()
        )


def test_weather_health_endpoint():
    data = get_json(
        f"{WEATHER_BASE}/health"
    )

    assert (
        data[
            "status"
        ]
        == "ok"
    )

    assert (
        data[
            "service"
        ]
        == "weather-data"
    )


def test_advisor_health_endpoint():
    data = get_json(
        f"{ADVISOR_BASE}/health"
    )

    assert (
        data[
            "status"
        ]
        == "ok"
    )

    assert (
        data[
            "service"
        ]
        == "advisor"
    )


def test_weather_endpoint_returns_two_periods():
    today = (
        datetime.now(
            ZoneInfo(
                "America/Chicago"
            )
        )
        .date()
        .isoformat()
    )

    query = urlencode(
        {
            "zip":
                "60616",

            "date":
                today,
        }
    )

    data = get_json(
        f"{WEATHER_BASE}/weather?"
        f"{query}"
    )

    assert (
        data[
            "zip"
        ]
        == "60616"
    )

    assert (
        data[
            "date"
        ]
        == today
    )

    assert (
        "morning"
        in data[
            "periods"
        ]
    )

    assert (
        "night"
        in data[
            "periods"
        ]
    )


def test_advisor_report_api_returns_complete_report():
    today = (
        datetime.now(
            ZoneInfo(
                "America/Chicago"
            )
        )
        .date()
        .isoformat()
    )

    query = urlencode(
        {
            "zip":
                "60616",

            "date":
                today,

            "clothing":
                "neutral",
        }
    )

    data = get_json(
        f"{ADVISOR_BASE}"
        f"/api/report?"
        f"{query}",
        timeout=25,
    )

    assert (
        data[
            "zip"
        ]
        == "60616"
    )

    for period_name in (
        "morning",
        "night",
    ):
        period = (
            data[
                period_name
            ]
        )

        assert (
            "facts"
            in period
        )

        assert (
            "advice"
            in period
        )

        advice = (
            period[
                "advice"
            ]
        )

        assert (
            advice[
                "road_conditions"
            ]
        )

        assert (
            advice[
                "dressing"
            ]
        )

        assert (
            advice[
                "accessories"
            ]
        )


def test_identical_report_is_cached_and_fast():
    today = (
        datetime.now(
            ZoneInfo(
                "America/Chicago"
            )
        )
        .date()
        .isoformat()
    )

    query = urlencode(
        {
            "zip":
                "60616",

            "date":
                today,

            "clothing":
                "neutral",
        }
    )

    url = (
        f"{ADVISOR_BASE}"
        f"/api/report?"
        f"{query}"
    )

    get_json(
        url,
        timeout=25,
    )

    started = (
        time.perf_counter()
    )

    data = get_json(
        url,
        timeout=10,
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    assert (
        data[
            "adviceCache"
        ]
        == "hit"
    )

    assert (
        elapsed
        < 3.0
    )


def test_invalid_zip_is_rejected():
    today = (
        datetime.now(
            ZoneInfo(
                "America/Chicago"
            )
        )
        .date()
        .isoformat()
    )

    query = urlencode(
        {
            "zip":
                "1234",

            "date":
                today,

            "clothing":
                "neutral",
        }
    )

    try:
        get_json(
            f"{ADVISOR_BASE}"
            f"/api/report?"
            f"{query}"
        )

    except HTTPError as err:
        assert (
            err.code
            in {
                400,
                422,
            }
        )

    else:
        raise AssertionError(
            "Invalid ZIP was not rejected."
        )
