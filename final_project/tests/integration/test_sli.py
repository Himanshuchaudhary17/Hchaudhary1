"""SLI test for the deployed Weather Advisor service."""

from __future__ import annotations

import http.client
import statistics
import time

from stack.config import Settings
from stack.outputs import StackOutputs


settings = Settings.from_file(".env")
outputs = StackOutputs.load()

HOST = outputs.alb_dns_name
PORT = settings.advisor.listener_port

SLO_MS = 120.0
SAMPLES = 20


def test_advisor_latency_slo():
    """
    Measure application response latency over a persistent
    HTTP connection to the public ALB.

    The initial connection/warm-up request is excluded.
    """

    connection = http.client.HTTPConnection(
        HOST,
        PORT,
        timeout=5,
    )

    # Warm-up + establish connection.
    connection.request(
        "GET",
        "/health",
    )

    response = connection.getresponse()

    assert response.status == 200

    response.read()

    latencies_ms = []

    for _ in range(SAMPLES):

        started = time.perf_counter()

        connection.request(
            "GET",
            "/health",
        )

        response = connection.getresponse()

        assert response.status == 200

        response.read()

        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000

        latencies_ms.append(
            elapsed_ms
        )

    connection.close()

    average_ms = statistics.mean(
        latencies_ms
    )

    median_ms = statistics.median(
        latencies_ms
    )

    minimum_ms = min(
        latencies_ms
    )

    maximum_ms = max(
        latencies_ms
    )

    sorted_values = sorted(
        latencies_ms
    )

    p95_index = max(
        0,
        int(
            0.95 *
            len(sorted_values)
        ) - 1,
    )

    p95_ms = sorted_values[
        p95_index
    ]

    print()
    print(
        "Weather Advisor SLI"
    )

    print(
        f"Endpoint: "
        f"http://{HOST}:{PORT}/health"
    )

    print(
        f"Samples: {SAMPLES}"
    )

    print(
        f"Minimum: {minimum_ms:.2f} ms"
    )

    print(
        f"Median:  {median_ms:.2f} ms"
    )

    print(
        f"Average: {average_ms:.2f} ms"
    )

    print(
        f"P95:     {p95_ms:.2f} ms"
    )

    print(
        f"Maximum: {maximum_ms:.2f} ms"
    )

    print(
        f"SLO target: {SLO_MS:.2f} ms average"
    )

    result = (
        "PASS"
        if average_ms <= SLO_MS
        else "FAIL"
    )

    print(
        f"SLO RESULT: {result}"
    )

    assert average_ms <= SLO_MS, (
        f"Average latency "
        f"{average_ms:.2f} ms "
        f"exceeded "
        f"{SLO_MS:.2f} ms SLO"
    )
