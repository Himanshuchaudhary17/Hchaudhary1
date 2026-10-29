"""Live infrastructure tests for the Weather Advisor stack.

Run after the deployed stack is healthy:

    pytest -q -m integration
"""

from __future__ import annotations

import pytest

from tests.helpers import wait_until

pytestmark = pytest.mark.integration


def test_load_balancer_is_public_and_spans_two_azs(
    aws,
    settings,
    outputs,
):
    lb = aws.elbv2.describe_load_balancers(
        LoadBalancerArns=[outputs.alb_arn]
    )["LoadBalancers"][0]

    assert lb["State"]["Code"] == "active"
    assert lb["Scheme"] == "internet-facing"

    zones = {
        az["ZoneName"]
        for az in lb["AvailabilityZones"]
    }

    assert zones == {
        settings.az_a,
        settings.az_b,
    }


def test_listeners_forward_to_correct_target_groups(
    aws,
    settings,
    outputs,
):
    listeners = aws.elbv2.describe_listeners(
        LoadBalancerArn=outputs.alb_arn
    )["Listeners"]

    forwards = {
        listener["Port"]:
        listener["DefaultActions"][0][
            "TargetGroupArn"
        ]
        for listener in listeners
    }

    assert (
        forwards[settings.weather.listener_port]
        == outputs.weather_tg_arn
    )

    assert (
        forwards[settings.advisor.listener_port]
        == outputs.advisor_tg_arn
    )


def test_target_groups_use_expected_health_checks(
    aws,
    settings,
    outputs,
):
    for tier in settings.tiers:
        tg = aws.elbv2.describe_target_groups(
            TargetGroupArns=[
                outputs.tg_arn(tier.name)
            ]
        )["TargetGroups"][0]

        assert tg["Port"] == settings.app_port
        assert tg["HealthCheckPath"] == "/"
        assert tg["HealthCheckIntervalSeconds"] == 10
        assert tg["HealthyThresholdCount"] == 2


def test_asgs_use_elb_health_and_two_subnets(
    aws,
    settings,
    outputs,
):
    for tier in settings.tiers:
        group = (
            aws.autoscaling
            .describe_auto_scaling_groups(
                AutoScalingGroupNames=[
                    tier.asg_name
                ]
            )["AutoScalingGroups"][0]
        )

        assert group["HealthCheckType"] == "ELB"
        assert group["DesiredCapacity"] == 1

        assert (
            set(
                group[
                    "VPCZoneIdentifier"
                ].split(",")
            )
            == {
                outputs.subnet_a,
                outputs.subnet_b,
            }
        )

        assert (
            outputs.tg_arn(tier.name)
            in group["TargetGroupARNs"]
        )


def test_app_port_is_reachable_only_from_alb(
    aws,
    settings,
    outputs,
):
    group = aws.ec2.describe_security_groups(
        GroupIds=[settings.app_sg_id]
    )["SecurityGroups"][0]

    rules = [
        permission
        for permission in group["IpPermissions"]
        if (
            permission.get("FromPort")
            == settings.app_port
        )
    ]

    assert rules, "port 3000 rule missing"

    for rule in rules:
        assert rule["IpRanges"] == []

        source_groups = [
            pair["GroupId"]
            for pair
            in rule["UserIdGroupPairs"]
        ]

        assert source_groups == [
            outputs.alb_security_group_id
        ]


def test_database_security_group_allows_only_5432_from_app(
    aws,
    settings,
):
    groups = aws.ec2.describe_security_groups(
        Filters=[
            {
                "Name": "group-name",
                "Values": [
                    settings.db_sg_name
                ],
            }
        ]
    )["SecurityGroups"]

    assert groups, "database security group not found"

    group = groups[0]

    rules = group["IpPermissions"]

    assert len(rules) == 1

    rule = rules[0]

    assert rule["IpProtocol"] == "tcp"
    assert rule["FromPort"] == settings.db_port
    assert rule["ToPort"] == settings.db_port

    assert rule["IpRanges"] == []
    assert rule["Ipv6Ranges"] == []

    source_groups = [
        pair["GroupId"]
        for pair
        in rule["UserIdGroupPairs"]
    ]

    assert source_groups == [
        settings.app_sg_id
    ]


def test_database_is_private_encrypted_single_az_no_backups(
    aws,
    settings,
):
    db = aws.rds.describe_db_instances(
        DBInstanceIdentifier=
            settings.db_instance_id
    )["DBInstances"][0]

    assert db["PubliclyAccessible"] is False
    assert db["MultiAZ"] is False
    assert db["StorageEncrypted"] is True
    assert db["BackupRetentionPeriod"] == 0

    assert db["DBInstanceClass"] == "db.t4g.micro"


def test_weather_role_reads_only_db_password(
    aws,
    settings,
):
    tier = settings.weather

    policy = aws.iam.get_role_policy(
        RoleName=tier.role_name,
        PolicyName=tier.policy_name,
    )["PolicyDocument"]

    statement = policy["Statement"][0]

    assert statement["Effect"] == "Allow"

    assert statement["Action"] == [
        "ssm:GetParameter"
    ]

    expected_suffix = (
        "parameter"
        f"{settings.db_password_param}"
    )

    assert statement["Resource"].endswith(
        expected_suffix
    )

    assert (
        settings.gemini_param_name
        not in statement["Resource"]
    )


def test_advisor_role_reads_only_gemini_key(
    aws,
    settings,
):
    tier = settings.advisor

    policy = aws.iam.get_role_policy(
        RoleName=tier.role_name,
        PolicyName=tier.policy_name,
    )["PolicyDocument"]

    statement = policy["Statement"][0]

    assert statement["Effect"] == "Allow"

    assert statement["Action"] == [
        "ssm:GetParameter"
    ]

    expected_suffix = (
        "parameter"
        f"{settings.gemini_param_name}"
    )

    assert statement["Resource"].endswith(
        expected_suffix
    )

    assert (
        settings.db_password_param
        not in statement["Resource"]
    )


def test_every_target_becomes_healthy(
    aws,
    settings,
    outputs,
):
    def all_healthy():
        for tier in settings.tiers:
            targets = (
                aws.elbv2
                .describe_target_health(
                    TargetGroupArn=
                        outputs.tg_arn(
                            tier.name
                        )
                )
                ["TargetHealthDescriptions"]
            )

            if not targets:
                return False

            if any(
                target[
                    "TargetHealth"
                ]["State"] != "healthy"
                for target in targets
            ):
                return False

        return True

    assert wait_until(
        all_healthy,
        timeout=420,
        interval=15,
    ), "targets never became healthy"
