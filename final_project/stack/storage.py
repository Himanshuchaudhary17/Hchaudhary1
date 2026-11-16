"""IAM roles and instance profiles for the Weather Advisor final project."""

from __future__ import annotations

import json
import logging

from .clients import AwsClients
from .config import Settings, Tier
from .policies import (
    policy_for,
    trust_policy,
)
from .util import ignore_errors


log = logging.getLogger("stack")


def parameter_arn(
    account_id: str,
    region: str,
    parameter_name: str,
) -> str:
    """Build the ARN for an SSM parameter."""

    return (
        f"arn:aws:ssm:{region}:{account_id}:"
        f"parameter{parameter_name}"
    )


def dynamodb_table_arn(
    account_id: str,
    region: str,
    table_name: str,
) -> str:
    """Build the ARN for a DynamoDB table."""

    return (
        f"arn:aws:dynamodb:{region}:{account_id}:"
        f"table/{table_name}"
    )


def sns_topic_arn(
    account_id: str,
    region: str,
    topic_name: str,
) -> str:
    """Build the ARN for the configured SNS topic."""

    return (
        f"arn:aws:sns:{region}:{account_id}:"
        f"{topic_name}"
    )


def ensure_role_and_profile(
    aws: AwsClients,
    settings: Settings,
    tier: Tier,
    account_id: str,
) -> None:
    """Create role, least-privilege policy, and instance profile."""

    weather_table_arn = dynamodb_table_arn(
        account_id,
        settings.region,
        settings.weather_table_name,
    )

    advisor_table_arn = dynamodb_table_arn(
        account_id,
        settings.region,
        settings.advisor_table_name,
    )

    gemini_parameter_arn = parameter_arn(
        account_id,
        settings.region,
        settings.gemini_param_name,
    )

    report_topic_arn = sns_topic_arn(
        account_id,
        settings.region,
        settings.sns_topic_name,
    )

    with ignore_errors(
        "EntityAlreadyExists"
    ):
        aws.iam.create_role(
            RoleName=tier.role_name,
            AssumeRolePolicyDocument=json.dumps(
                trust_policy()
            ),
        )

    aws.iam.put_role_policy(
        RoleName=tier.role_name,
        PolicyName=tier.policy_name,
        PolicyDocument=json.dumps(
            policy_for(
                tier.name,
                weather_table_arn,
                advisor_table_arn,
                gemini_parameter_arn,
                report_topic_arn,
            )
        ),
    )

    with ignore_errors(
        "EntityAlreadyExists"
    ):
        aws.iam.create_instance_profile(
            InstanceProfileName=(
                tier.profile_name
            )
        )

    profile = aws.iam.get_instance_profile(
        InstanceProfileName=(
            tier.profile_name
        )
    )

    roles = [
        role["RoleName"]
        for role in (
            profile[
                "InstanceProfile"
            ][
                "Roles"
            ]
        )
    ]

    if tier.role_name not in roles:
        aws.iam.add_role_to_instance_profile(
            InstanceProfileName=(
                tier.profile_name
            ),
            RoleName=(
                tier.role_name
            ),
        )

    log.info(
        "%s role and instance profile are ready.",
        tier.name,
    )


def delete_role_and_profile(
    aws: AwsClients,
    tier: Tier,
) -> None:
    """Remove one role, policy, and instance profile."""

    with ignore_errors(
        "NoSuchEntity"
    ):
        aws.iam.remove_role_from_instance_profile(
            InstanceProfileName=(
                tier.profile_name
            ),
            RoleName=tier.role_name,
        )

    with ignore_errors(
        "NoSuchEntity"
    ):
        aws.iam.delete_instance_profile(
            InstanceProfileName=(
                tier.profile_name
            )
        )

    with ignore_errors(
        "NoSuchEntity"
    ):
        aws.iam.delete_role_policy(
            RoleName=tier.role_name,
            PolicyName=tier.policy_name,
        )

    with ignore_errors(
        "NoSuchEntity"
    ):
        aws.iam.delete_role(
            RoleName=tier.role_name
        )

    log.info(
        "Removed %s role and instance profile.",
        tier.name,
    )
