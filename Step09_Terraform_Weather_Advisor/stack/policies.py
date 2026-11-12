"""IAM policy documents for the Weather Advisor stack."""

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


def ssm_parameter_policy(parameter_arn: str) -> dict:
    """Allow reading exactly one SSM parameter."""

    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter"
                ],
                "Resource": parameter_arn,
            }
        ],
    }


def weather_policy(db_password_arn: str) -> dict:
    """Weather tier may read only the database password."""

    return ssm_parameter_policy(db_password_arn)


def advisor_policy(gemini_parameter_arn: str) -> dict:
    """Advisor tier may read only the Gemini API key."""

    return ssm_parameter_policy(gemini_parameter_arn)


def policy_for(
    tier_name: str,
    db_password_arn: str,
    gemini_parameter_arn: str,
) -> dict:
    """Return the correct least-privilege policy for a tier."""

    if tier_name == "weather":
        return weather_policy(db_password_arn)

    if tier_name == "advisor":
        return advisor_policy(gemini_parameter_arn)

    raise ValueError(f"Unknown tier: {tier_name}")
