"""Integration tests for the Weather Advisor applications.

Run after the live stack is healthy:

    pytest -q -m integration
"""

from __future__ import annotations

import pytest
import requests

from tests.helpers import tier_url

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def weather_url(settings, outputs):
    return tier_url(
        outputs,
        settings,
        "weather",
    )


@pytest.fixture(scope="module")
def advisor_url(settings, outputs):
    return tier_url(
        outputs,
        settings,
        "advisor",
    )


def test_weather_root_is_available(weather_url):
    response = requests.get(
        weather_url,
        timeout=10,
    )

    assert response.status_code == 200

    body = response.json()

    assert body.get("service") == "weather"


def test_weather_valid_zip_returns_forecast(weather_url):
    response = requests.get(
        weather_url + "weather",
        params={"zip": "60616"},
        timeout=15,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["zip"] == "60616"
    assert body["city"] == "Chicago"
    assert body["state"] == "IL"

    assert "forecast" in body
    assert "temperature" in body["forecast"]
    assert "shortForecast" in body["forecast"]

    assert body["cache"] in (
        "hit",
        "miss",
        "unavailable",
    )


def test_weather_second_lookup_can_use_cache(weather_url):
    first = requests.get(
        weather_url + "weather",
        params={"zip": "60616"},
        timeout=15,
    )

    second = requests.get(
        weather_url + "weather",
        params={"zip": "60616"},
        timeout=15,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    body = second.json()

    assert body["zip"] == "60616"
    assert body["cache"] == "hit"


def test_weather_history_returns_rows(weather_url):
    response = requests.get(
        weather_url + "history",
        timeout=10,
    )

    assert response.status_code == 200

    body = response.json()

    assert "count" in body
    assert "lookups" in body

    assert isinstance(
        body["lookups"],
        list,
    )


def test_weather_invalid_zip_returns_400(weather_url):
    response = requests.get(
        weather_url + "weather",
        params={"zip": "123"},
        timeout=10,
    )

    assert response.status_code == 400


def test_weather_unknown_zip_returns_404(weather_url):
    response = requests.get(
        weather_url + "weather",
        params={"zip": "00000"},
        timeout=10,
    )

    assert response.status_code == 404

    body = response.json()

    assert body["error"] == "zip_not_found"


def test_advisor_root_is_available(advisor_url):
    response = requests.get(
        advisor_url,
        timeout=10,
    )

    assert response.status_code == 200

    assert "Weather Advisor" in response.text


def test_advisor_returns_advice(advisor_url):
    response = requests.get(
        advisor_url + "advice",
        params={"zip": "60616"},
        timeout=20,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["zip"] == "60616"
    assert body["city"] == "Chicago"

    assert "forecast" in body
    assert "advice" in body

    assert body["source"] in (
        "gemini",
        "fallback",
    )

    if body["source"] == "gemini":
        assert body["model"]
    else:
        assert body["model"] is None
