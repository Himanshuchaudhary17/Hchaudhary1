"""DynamoDB resources for the Weather Advisor final project."""

from __future__ import annotations

import logging

from botocore.exceptions import ClientError

from .clients import AwsClients
from .config import Settings


log = logging.getLogger("stack")


def table_exists(
    aws: AwsClients,
    table_name: str,
) -> bool:
    """Return True when a DynamoDB table exists."""

    try:
        aws.dynamodb.describe_table(
            TableName=table_name
        )

        return True

    except ClientError as err:
        if (
            err.response["Error"]["Code"]
            != "ResourceNotFoundException"
        ):
            raise

        return False


def ensure_table(
    aws: AwsClients,
    table_name: str,
) -> None:
    """Create one on-demand DynamoDB table with TTL."""

    if not table_exists(
        aws,
        table_name,
    ):
        aws.dynamodb.create_table(
            TableName=table_name,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {
                    "AttributeName": "pk",
                    "AttributeType": "S",
                }
            ],
            KeySchema=[
                {
                    "AttributeName": "pk",
                    "KeyType": "HASH",
                }
            ],
        )

        waiter = (
            aws.dynamodb
            .get_waiter(
                "table_exists"
            )
        )

        waiter.wait(
            TableName=table_name
        )

        log.info(
            "Created DynamoDB table %s.",
            table_name,
        )

    else:
        log.info(
            "DynamoDB table %s already exists.",
            table_name,
        )

    ttl = (
        aws.dynamodb
        .describe_time_to_live(
            TableName=table_name
        )
        .get(
            "TimeToLiveDescription",
            {},
        )
    )

    status = ttl.get(
        "TimeToLiveStatus"
    )

    attribute_name = ttl.get(
        "AttributeName"
    )

    if (
        status not in (
            "ENABLED",
            "ENABLING",
        )
        or attribute_name
        != "expiresAt"
    ):
        try:
            aws.dynamodb.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    "Enabled": True,
                    "AttributeName": "expiresAt",
                },
            )

            log.info(
                "Enabled TTL on %s using expiresAt.",
                table_name,
            )

        except ClientError as err:
            code = (
                err.response[
                    "Error"
                ]["Code"]
            )

            if code != "ValidationException":
                raise


def ensure_weather_table(
    aws: AwsClients,
    settings: Settings,
) -> None:
    """Create the Weather cache table."""

    ensure_table(
        aws,
        settings.weather_table_name,
    )


def ensure_advisor_table(
    aws: AwsClients,
    settings: Settings,
) -> None:
    """Create the Advisor state table."""

    ensure_table(
        aws,
        settings.advisor_table_name,
    )


def delete_table(
    aws: AwsClients,
    table_name: str,
) -> None:
    """Delete one DynamoDB table if it exists."""

    if not table_exists(
        aws,
        table_name,
    ):
        log.info(
            "DynamoDB table %s already absent.",
            table_name,
        )

        return

    aws.dynamodb.delete_table(
        TableName=table_name
    )

    waiter = (
        aws.dynamodb
        .get_waiter(
            "table_not_exists"
        )
    )

    waiter.wait(
        TableName=table_name
    )

    log.info(
        "Deleted DynamoDB table %s.",
        table_name,
    )


def delete_weather_table(
    aws: AwsClients,
    settings: Settings,
) -> None:
    """Delete the Weather cache table."""

    delete_table(
        aws,
        settings.weather_table_name,
    )


def delete_advisor_table(
    aws: AwsClients,
    settings: Settings,
) -> None:
    """Delete the Advisor state table."""

    delete_table(
        aws,
        settings.advisor_table_name,
    )
