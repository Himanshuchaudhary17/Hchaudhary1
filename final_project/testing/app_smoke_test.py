#!/usr/bin/env python3

"""Smoke test the current Weather Advisor application through the public ALB."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines from an .env-style file."""

    values = {}

    for line in path.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def get(url: str, timeout: int = 30):
    """Return (status, parsed JSON or text)."""

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode()
            status = response.status

    except urllib.error.HTTPError as err:
        body = err.read().decode()
        status = err.code

    except (urllib.error.URLError, TimeoutError) as err:
        return 0, {
            "error": f"no connection: {err}"
        }

    try:
        return status, json.loads(body)

    except ValueError:
        return status, body


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--zip",
        default="60616",
        help="US ZIP code for happy-path checks",
    )

    args = parser.parse_args()

    env = load_dotenv(PROJECT_DIR / ".env")
    outputs = load_dotenv(PROJECT_DIR / "stack_outputs.env")

    alb = outputs["ALB_DNS_NAME"]

    weather = (
        f"http://{alb}:"
        f"{env['WEATHER_LISTENER_PORT']}"
    )

    advisor = (
        f"http://{alb}:"
        f"{env['ADVISOR_LISTENER_PORT']}"
    )

    today = datetime.now(
        ZoneInfo("America/Chicago")
    ).date().isoformat()

    results = []

    def check(name, ok, detail=""):
        results.append(bool(ok))

        print(
            f"{'PASS' if ok else 'FAIL'}  "
            f"{name}  {detail}"
        )

    print("\nWeather Advisor Smoke Test")
    print(f"ALB: {alb}")
    print(f"Date: {today}\n")

    # -------------------------------------------------
    # Health checks
    # -------------------------------------------------

    status, body = get(
        f"{weather}/health"
    )

    check(
        "weather health endpoint",
        status == 200
        and isinstance(body, dict)
        and body.get("status") == "ok"
        and body.get("service") == "weather-data",
        f"status={status}",
    )

    status, body = get(
        f"{advisor}/health"
    )

    check(
        "advisor health endpoint",
        status == 200
        and isinstance(body, dict)
        and body.get("status") == "ok"
        and body.get("service") == "advisor",
        f"status={status}",
    )

    # -------------------------------------------------
    # Weather happy path
    # -------------------------------------------------

    weather_query = urllib.parse.urlencode(
        {
            "zip": args.zip,
            "date": today,
        }
    )

    weather_url = (
        f"{weather}/weather?"
        f"{weather_query}"
    )

    status, body = get(
        weather_url,
        timeout=30,
    )

    weather_ok = (
        status == 200
        and isinstance(body, dict)
        and body.get("zip") == args.zip
        and body.get("date") == today
        and "morning" in body.get("periods", {})
        and "night" in body.get("periods", {})
    )

    check(
        "weather returns morning and night forecast facts",
        weather_ok,
        (
            f"status={status}, "
            f"cache={body.get('cache') if isinstance(body, dict) else '?'}"
        ),
    )

    # Repeat request to verify weather cache.
    status, body = get(
        weather_url,
        timeout=20,
    )

    check(
        "repeat weather request is a cache hit",
        status == 200
        and isinstance(body, dict)
        and body.get("cache") == "hit",
        (
            f"status={status}, "
            f"cache={body.get('cache') if isinstance(body, dict) else '?'}"
        ),
    )

    # -------------------------------------------------
    # Weather validation
    # -------------------------------------------------

    bad_weather_query = urllib.parse.urlencode(
        {
            "zip": "1234",
            "date": today,
        }
    )

    status, body = get(
        f"{weather}/weather?{bad_weather_query}"
    )

    check(
        "weather rejects invalid ZIP",
        status == 400,
        f"status={status}",
    )

    unknown_weather_query = urllib.parse.urlencode(
        {
            "zip": "00000",
            "date": today,
        }
    )

    status, body = get(
        f"{weather}/weather?{unknown_weather_query}"
    )

    check(
        "weather rejects unknown ZIP",
        status == 404,
        f"status={status}",
    )

    # -------------------------------------------------
    # Advisor report
    # -------------------------------------------------

    advisor_query = urllib.parse.urlencode(
        {
            "zip": args.zip,
            "date": today,
            "clothing": "neutral",
        }
    )

    advisor_url = (
        f"{advisor}/api/report?"
        f"{advisor_query}"
    )

    started = time.perf_counter()

    status, body = get(
        advisor_url,
        timeout=30,
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    advisor_ok = (
        status == 200
        and isinstance(body, dict)
        and "morning" in body
        and "night" in body
    )

    if advisor_ok:
        for period_name in (
            "morning",
            "night",
        ):
            period = body.get(
                period_name,
                {},
            )

            advice = period.get(
                "advice",
                {},
            )

            if not (
                "facts" in period
                and advice.get("road_conditions")
                and advice.get("dressing")
                and advice.get("accessories")
            ):
                advisor_ok = False

    check(
        "advisor returns complete morning and night report",
        advisor_ok,
        f"status={status}, elapsed={elapsed:.2f}s",
    )

    if advisor_ok:
        print(
            "      morning source="
            f"{body['morning']['advice'].get('source')}"
        )

        print(
            "      night source="
            f"{body['night']['advice'].get('source')}"
        )

    # -------------------------------------------------
    # Advisor report cache
    # -------------------------------------------------

    started = time.perf_counter()

    status, body = get(
        advisor_url,
        timeout=15,
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    check(
        "repeat advisor report uses report cache",
        status == 200
        and isinstance(body, dict)
        and body.get("adviceCache") == "hit",
        (
            f"status={status}, "
            f"adviceCache="
            f"{body.get('adviceCache') if isinstance(body, dict) else '?'}, "
            f"elapsed={elapsed:.2f}s"
        ),
    )

    # -------------------------------------------------
    # Advisor validation
    # -------------------------------------------------

    bad_advisor_query = urllib.parse.urlencode(
        {
            "zip": "1234",
            "date": today,
            "clothing": "neutral",
        }
    )

    status, body = get(
        f"{advisor}/api/report?"
        f"{bad_advisor_query}"
    )

    check(
        "advisor rejects invalid ZIP",
        status in {400, 422},
        f"status={status}",
    )

    # -------------------------------------------------
    # Advisor web page
    # -------------------------------------------------

    status, body = get(
        f"{advisor}/"
    )

    check(
        "advisor home page loads",
        status == 200
        and isinstance(body, str)
        and "<form" in body
        and "Weather Advisor" in body,
        f"status={status}",
    )

    # -------------------------------------------------
    # Summary
    # -------------------------------------------------

    passed = sum(results)
    total = len(results)

    print(
        f"\n{passed} of {total} smoke checks passed"
    )

    sys.exit(
        0 if all(results) else 1
    )


if __name__ == "__main__":
    main()
