"""Chaos tests for the Weather Advisor stack.

These tests modify live AWS resources.

Run only when the stack is deployed:

    pytest -q -m chaos -s
"""

from __future__ import annotations

import time

import pytest
import requests

from tests.helpers import tier_url

pytestmark = pytest.mark.chaos

RECOVERY_LIMIT_SECONDS = 300


def _weather_url(settings, outputs):
    return tier_url(
        outputs,
        settings,
        "weather",
    )


def _advisor_url(settings, outputs):
    return tier_url(
        outputs,
        settings,
        "advisor",
    )


def _in_service_weather_instance(
    aws,
    settings,
):
    group = (
        aws.autoscaling
        .describe_auto_scaling_groups(
            AutoScalingGroupNames=[
                settings.weather.asg_name
            ]
        )["AutoScalingGroups"][0]
    )

    for instance in group["Instances"]:
        if (
            instance["LifecycleState"]
            == "InService"
        ):
            return instance["InstanceId"]

    return None


def _db_security_group_id(
    aws,
    settings,
):
    groups = (
        aws.ec2
        .describe_security_groups(
            Filters=[
                {
                    "Name": "group-name",
                    "Values": [
                        settings.db_sg_name
                    ],
                }
            ]
        )["SecurityGroups"]
    )

    assert groups, "DB security group not found"

    return groups[0]["GroupId"]


def test_weather_survives_database_outage(
    aws,
    settings,
    outputs,
):
    """Weather must still work if PostgreSQL is unreachable."""

    weather_url = _weather_url(
        settings,
        outputs,
    )

    db_sg_id = _db_security_group_id(
        aws,
        settings,
    )

    permission = {
        "IpProtocol": "tcp",
        "FromPort": settings.db_port,
        "ToPort": settings.db_port,
        "UserIdGroupPairs": [
            {
                "GroupId":
                    settings.app_sg_id
            }
        ],
    }

    try:
        aws.ec2.revoke_security_group_ingress(
            GroupId=db_sg_id,
            IpPermissions=[permission],
        )

        time.sleep(5)

        response = requests.get(
            weather_url + "weather",
            params={"zip": "10001"},
            timeout=20,
        )

        print(
            "\nDB outage response:",
            response.status_code,
            response.text,
        )

        assert response.status_code == 200

        body = response.json()

        assert body["zip"] == "10001"
        assert body["cache"] == "unavailable"

    finally:
        try:
            aws.ec2.authorize_security_group_ingress(
                GroupId=db_sg_id,
                IpPermissions=[permission],
            )
        except Exception as exc:
            if (
                "InvalidPermission.Duplicate"
                not in str(exc)
            ):
                raise


def test_weather_instance_failure_causes_502_then_recovers(
    aws,
    settings,
    outputs,
):
    """Advisor should return 502 during Weather outage and recover."""

    weather_url = _weather_url(
        settings,
        outputs,
    )

    advisor_url = _advisor_url(
        settings,
        outputs,
    )

    victim = _in_service_weather_instance(
        aws,
        settings,
    )

    assert victim, (
        "No in-service Weather instance found"
    )

    # Confirm healthy before chaos begins.
    before = requests.get(
        weather_url + "weather",
        params={"zip": "60616"},
        timeout=15,
    )

    assert before.status_code == 200

    aws.ec2.terminate_instances(
        InstanceIds=[victim]
    )

    started = time.time()

    saw_502 = False
    recovered_after = None

    while (
        time.time() - started
        < RECOVERY_LIMIT_SECONDS
    ):
        try:
            advisor_response = requests.get(
                advisor_url + "advice",
                params={"zip": "60616"},
                timeout=5,
            )

            if (
                advisor_response.status_code
                == 502
            ):
                saw_502 = True

        except requests.RequestException:
            pass

        try:
            weather_response = requests.get(
                weather_url + "weather",
                params={"zip": "60616"},
                timeout=5,
            )

            if (
                saw_502
                and weather_response.status_code
                == 200
            ):
                recovered_after = (
                    time.time() - started
                )
                break

        except requests.RequestException:
            pass

        time.sleep(3)

    print(
        f"\nTerminated Weather instance: "
        f"{victim}"
    )

    print(
        f"Saw Advisor 502: {saw_502}"
    )

    print(
        f"Weather recovery time: "
        f"{recovered_after}s"
    )

    assert saw_502, (
        "Advisor never returned 502 "
        "during the Weather outage"
    )

    assert recovered_after is not None, (
        "Weather did not recover "
        "within 300 seconds"
    )

    assert (
        recovered_after
        <= RECOVERY_LIMIT_SECONDS
    )
