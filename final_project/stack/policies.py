"""Least-privilege IAM policies for the Weather Advisor final project."""

from __future__ import annotations


def trust_policy() -> dict:
    """Allow EC2 instances to assume the role."""

    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
            }
        ],
    }


def weather_policy(
    weather_table_arn: str,
) -> dict:
    """Allow Weather tier access only to its DynamoDB cache table."""

    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "WeatherCacheAccess",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                ],
                "Resource": weather_table_arn,
            }
        ],
    }


def advisor_policy(
    advisor_table_arn: str,
    gemini_parameter_arn: str,
    sns_topic_arn: str,
) -> dict:
    """Allow Advisor access only to required state, secret, and SNS topic."""

    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AdvisorStateAccess",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                ],
                "Resource": advisor_table_arn,
            },
            {
                "Sid": "GeminiParameterRead",
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter",
                ],
                "Resource": gemini_parameter_arn,
            },
            {
                "Sid": "ReportEmailTopicAccess",
                "Effect": "Allow",
                "Action": [
                    "sns:Subscribe",
                    "sns:Publish",
                    "sns:ListSubscriptionsByTopic",
                ],
                "Resource": sns_topic_arn,
            },
        ],
    }


def policy_for(
    tier_name: str,
    weather_table_arn: str,
    advisor_table_arn: str,
    gemini_parameter_arn: str,
    sns_topic_arn: str,
) -> dict:
    """Return the least-privilege policy for one tier."""

    if tier_name == "weather":
        return weather_policy(
            weather_table_arn
        )

    if tier_name == "advisor":
        return advisor_policy(
            advisor_table_arn,
            gemini_parameter_arn,
            sns_topic_arn,
        )

    raise ValueError(
        f"Unknown tier: {tier_name}"
    )
