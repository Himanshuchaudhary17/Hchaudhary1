"""Unit tests for least-privilege IAM policies."""

from __future__ import annotations

import pytest

from stack.policies import (
    advisor_policy,
    policy_for,
    trust_policy,
    weather_policy,
)


WEATHER_TABLE_ARN = (
    "arn:aws:dynamodb:us-east-2:"
    "123456789012:"
    "table/test-weather-cache"
)

ADVISOR_TABLE_ARN = (
    "arn:aws:dynamodb:us-east-2:"
    "123456789012:"
    "table/test-advisor-state"
)

GEMINI_ARN = (
    "arn:aws:ssm:us-east-2:"
    "123456789012:"
    "parameter/itmo-544/final/"
    "gemini-api-key"
)

SNS_ARN = (
    "arn:aws:sns:us-east-2:"
    "123456789012:"
    "test-weather-reports"
)


def test_trust_policy_allows_only_ec2():
    statement = (
        trust_policy()[
            "Statement"
        ][0]
    )

    assert (
        statement["Effect"]
        == "Allow"
    )

    assert (
        statement["Principal"]
        == {
            "Service":
                "ec2.amazonaws.com"
        }
    )

    assert (
        statement["Action"]
        == "sts:AssumeRole"
    )


def test_weather_policy_uses_only_weather_table():
    policy = weather_policy(
        WEATHER_TABLE_ARN
    )

    statement = (
        policy[
            "Statement"
        ][0]
    )

    assert statement["Action"] == [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
    ]

    assert (
        statement["Resource"]
        == WEATHER_TABLE_ARN
    )


def test_advisor_policy_has_required_resources():
    policy = advisor_policy(
        ADVISOR_TABLE_ARN,
        GEMINI_ARN,
        SNS_ARN,
    )

    statements = (
        policy[
            "Statement"
        ]
    )

    resources = {
        statement["Resource"]
        for statement
        in statements
    }

    assert resources == {
        ADVISOR_TABLE_ARN,
        GEMINI_ARN,
        SNS_ARN,
    }


def test_advisor_policy_has_required_actions():
    policy = advisor_policy(
        ADVISOR_TABLE_ARN,
        GEMINI_ARN,
        SNS_ARN,
    )

    actions = set()

    for statement in (
        policy[
            "Statement"
        ]
    ):
        actions.update(
            statement[
                "Action"
            ]
        )

    assert (
        "dynamodb:GetItem"
        in actions
    )

    assert (
        "dynamodb:PutItem"
        in actions
    )

    assert (
        "dynamodb:UpdateItem"
        in actions
    )

    assert (
        "ssm:GetParameter"
        in actions
    )

    assert (
        "sns:Subscribe"
        in actions
    )

    assert (
        "sns:Publish"
        in actions
    )


def test_policies_have_no_wildcard_resources():
    policies = [
        weather_policy(
            WEATHER_TABLE_ARN
        ),

        advisor_policy(
            ADVISOR_TABLE_ARN,
            GEMINI_ARN,
            SNS_ARN,
        ),
    ]

    for policy in policies:
        for statement in (
            policy[
                "Statement"
            ]
        ):
            assert (
                statement[
                    "Resource"
                ]
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

            assert "*" not in actions


def test_policy_for_weather():
    result = policy_for(
        "weather",
        WEATHER_TABLE_ARN,
        ADVISOR_TABLE_ARN,
        GEMINI_ARN,
        SNS_ARN,
    )

    assert (
        result
        == weather_policy(
            WEATHER_TABLE_ARN
        )
    )


def test_policy_for_advisor():
    result = policy_for(
        "advisor",
        WEATHER_TABLE_ARN,
        ADVISOR_TABLE_ARN,
        GEMINI_ARN,
        SNS_ARN,
    )

    assert (
        result
        == advisor_policy(
            ADVISOR_TABLE_ARN,
            GEMINI_ARN,
            SNS_ARN,
        )
    )


def test_policy_for_rejects_unknown_tier():
    with pytest.raises(
        ValueError,
        match="Unknown tier",
    ):
        policy_for(
            "unknown",
            WEATHER_TABLE_ARN,
            ADVISOR_TABLE_ARN,
            GEMINI_ARN,
            SNS_ARN,
        )
