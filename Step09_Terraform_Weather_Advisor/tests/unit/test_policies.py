import pytest

from stack.policies import (
    advisor_policy,
    policy_for,
    ssm_parameter_policy,
    trust_policy,
    weather_policy,
)


DB_ARN = (
    "arn:aws:ssm:us-east-2:123456789012:"
    "parameter/itmo-444-544/db-password"
)

GEMINI_ARN = (
    "arn:aws:ssm:us-east-2:123456789012:"
    "parameter/itmo-444-544/gemini-api-key"
)


def test_trust_policy_allows_only_ec2():
    statement = trust_policy()["Statement"][0]

    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {
        "Service": "ec2.amazonaws.com"
    }
    assert statement["Action"] == "sts:AssumeRole"


def test_ssm_parameter_policy_allows_only_get_parameter():
    policy = ssm_parameter_policy(DB_ARN)

    statement = policy["Statement"][0]

    assert statement["Effect"] == "Allow"
    assert statement["Action"] == [
        "ssm:GetParameter"
    ]
    assert statement["Resource"] == DB_ARN


def test_weather_policy_reads_only_db_password():
    policy = weather_policy(DB_ARN)

    statement = policy["Statement"][0]

    assert statement["Action"] == [
        "ssm:GetParameter"
    ]
    assert statement["Resource"] == DB_ARN
    assert statement["Resource"] != GEMINI_ARN


def test_advisor_policy_reads_only_gemini_key():
    policy = advisor_policy(GEMINI_ARN)

    statement = policy["Statement"][0]

    assert statement["Action"] == [
        "ssm:GetParameter"
    ]
    assert statement["Resource"] == GEMINI_ARN
    assert statement["Resource"] != DB_ARN


def test_policy_for_returns_weather_policy():
    assert policy_for(
        "weather",
        DB_ARN,
        GEMINI_ARN,
    ) == weather_policy(DB_ARN)


def test_policy_for_returns_advisor_policy():
    assert policy_for(
        "advisor",
        DB_ARN,
        GEMINI_ARN,
    ) == advisor_policy(GEMINI_ARN)


def test_policy_for_rejects_unknown_tier():
    with pytest.raises(
        ValueError,
        match="Unknown tier",
    ):
        policy_for(
            "unknown",
            DB_ARN,
            GEMINI_ARN,
        )
