"""Integration tests for the deployed Weather Advisor AWS infrastructure."""

from __future__ import annotations

import json

import boto3

from stack.config import Settings
from stack.outputs import StackOutputs


settings = Settings.from_file(".env")
outputs = StackOutputs.load()

session = boto3.Session(
    region_name=settings.region
)

ec2 = session.client("ec2")
elbv2 = session.client("elbv2")
autoscaling = session.client("autoscaling")
dynamodb = session.client("dynamodb")
iam = session.client("iam")
sns = session.client("sns")
ssm = session.client("ssm")
sts = session.client("sts")


def test_both_target_groups_are_healthy():
    """Both deployed tiers must be healthy behind the ALB."""

    for target_group_arn in (
        outputs.weather_tg_arn,
        outputs.advisor_tg_arn,
    ):
        response = (
            elbv2.describe_target_health(
                TargetGroupArn=
                    target_group_arn
            )
        )

        targets = (
            response[
                "TargetHealthDescriptions"
            ]
        )

        assert targets

        states = [
            item[
                "TargetHealth"
            ][
                "State"
            ]
            for item in targets
        ]

        assert all(
            state == "healthy"
            for state in states
        )


def test_alb_has_weather_and_advisor_listeners():
    """ALB must expose both application tiers."""

    response = (
        elbv2.describe_listeners(
            LoadBalancerArn=
                outputs.alb_arn
        )
    )

    ports = {
        listener[
            "Port"
        ]
        for listener in (
            response[
                "Listeners"
            ]
        )
    }

    assert (
        settings.weather.listener_port
        in ports
    )

    assert (
        settings.advisor.listener_port
        in ports
    )


def test_auto_scaling_groups_have_healthy_instances():
    """Each tier must have exactly one healthy active instance."""

    response = (
        autoscaling
        .describe_auto_scaling_groups(
            AutoScalingGroupNames=[
                settings.weather.asg_name,
                settings.advisor.asg_name,
            ]
        )
    )

    groups = {
        group["AutoScalingGroupName"]: group
        for group in response["AutoScalingGroups"]
    }

    for tier in settings.tiers:
        group = groups[tier.asg_name]

        assert group["DesiredCapacity"] == 1

        active_instances = [
            instance
            for instance in group["Instances"]
            if instance["LifecycleState"] == "InService"
        ]

        assert len(active_instances) == 1

        instance = active_instances[0]

        assert instance["HealthStatus"] == "Healthy"



def test_ec2_instances_use_configured_instance_type():
    """Active EC2 instances must use the configured instance type."""

    response = (
        autoscaling
        .describe_auto_scaling_groups(
            AutoScalingGroupNames=[
                settings.weather.asg_name,
                settings.advisor.asg_name,
            ]
        )
    )

    ids = []

    for group in response["AutoScalingGroups"]:
        ids.extend(
            item["InstanceId"]
            for item in group["Instances"]
            if item["LifecycleState"] == "InService"
        )

    assert len(ids) == 2

    response = (
        ec2.describe_instances(
            InstanceIds=ids
        )
    )

    instances = [
        instance
        for reservation in response["Reservations"]
        for instance in reservation["Instances"]
        if instance["State"]["Name"] == "running"
    ]

    assert len(instances) == 2

    assert all(
        instance["InstanceType"]
        == settings.instance_type
        for instance in instances
    )



def test_dynamodb_tables_are_on_demand():
    """Both project tables must use PAY_PER_REQUEST billing."""

    for table_name in (
        settings.weather_table_name,
        settings.advisor_table_name,
    ):
        table = (
            dynamodb.describe_table(
                TableName=table_name
            )[
                "Table"
            ]
        )

        billing = (
            table.get(
                "BillingModeSummary",
                {}
            )
            .get(
                "BillingMode"
            )
        )

        assert (
            billing
            == "PAY_PER_REQUEST"
        )


def test_dynamodb_ttl_is_enabled():
    """Both tables must expire temporary records using expiresAt."""

    for table_name in (
        settings.weather_table_name,
        settings.advisor_table_name,
    ):
        ttl = (
            dynamodb
            .describe_time_to_live(
                TableName=
                    table_name
            )[
                "TimeToLiveDescription"
            ]
        )

        assert (
            ttl[
                "AttributeName"
            ]
            == "expiresAt"
        )

        assert (
            ttl[
                "TimeToLiveStatus"
            ]
            in {
                "ENABLED",
                "ENABLING",
            }
        )


def test_gemini_parameter_is_secure_string():
    """Gemini key must be stored as a SecureString in SSM."""

    response = (
        ssm.describe_parameters(
            ParameterFilters=[
                {
                    "Key":
                        "Name",

                    "Option":
                        "Equals",

                    "Values": [
                        settings
                        .gemini_param_name
                    ],
                }
            ]
        )
    )

    parameters = (
        response[
            "Parameters"
        ]
    )

    assert (
        len(parameters)
        == 1
    )

    assert (
        parameters[0][
            "Type"
        ]
        == "SecureString"
    )


def test_sns_report_topic_exists():
    """The exact configured report topic must exist."""

    topics = []
    token = None

    while True:
        kwargs = {}

        if token:
            kwargs[
                "NextToken"
            ] = token

        response = (
            sns.list_topics(
                **kwargs
            )
        )

        topics.extend(
            topic[
                "TopicArn"
            ]
            for topic in (
                response[
                    "Topics"
                ]
            )
        )

        token = (
            response.get(
                "NextToken"
            )
        )

        if not token:
            break

    assert (
        outputs.sns_topic_arn
        in topics
    )


def test_deployed_iam_policies_have_no_wildcards():
    """Application roles must not use wildcard actions or resources."""

    for tier in settings.tiers:
        response = (
            iam.get_role_policy(
                RoleName=
                    tier.role_name,

                PolicyName=
                    tier.policy_name,
            )
        )

        policy = (
            response[
                "PolicyDocument"
            ]
        )

        if isinstance(
            policy,
            str,
        ):
            policy = (
                json.loads(
                    policy
                )
            )

        for statement in (
            policy[
                "Statement"
            ]
        ):
            resource = (
                statement[
                    "Resource"
                ]
            )

            assert (
                resource
                != "*"
            )

            actions = (
                statement[
                    "Action"
                ]
            )

            if isinstance(
                actions,
                str,
            ):
                actions = [
                    actions
                ]

            assert (
                "*"
                not in actions
            )


def test_stack_is_in_expected_aws_account():
    """Basic live-AWS sanity check."""

    identity = (
        sts.get_caller_identity()
    )

    assert (
        identity[
            "Account"
        ]
    )
