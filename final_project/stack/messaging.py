"""SNS resources for the Weather Advisor final project."""

from __future__ import annotations

import logging

from .clients import AwsClients
from .config import Settings


log = logging.getLogger("stack")


def ensure_report_topic(
    aws: AwsClients,
    settings: Settings,
) -> str:
    """Create or return the SNS topic used for weather reports."""

    response = aws.sns.create_topic(
        Name=settings.sns_topic_name
    )

    topic_arn = response["TopicArn"]

    log.info(
        "SNS report topic is ready: %s",
        topic_arn,
    )

    return topic_arn


def find_topic_arn(
    aws: AwsClients,
    settings: Settings,
) -> str | None:
    """Find the configured SNS topic ARN if it exists."""

    paginator = aws.sns.get_paginator(
        "list_topics"
    )

    suffix = (
        f":{settings.sns_topic_name}"
    )

    for page in paginator.paginate():
        for topic in page.get(
            "Topics",
            [],
        ):
            arn = topic.get(
                "TopicArn",
                "",
            )

            if arn.endswith(
                suffix
            ):
                return arn

    return None


def delete_report_topic(
    aws: AwsClients,
    settings: Settings,
) -> None:
    """Delete the SNS report topic if present."""

    topic_arn = find_topic_arn(
        aws,
        settings,
    )

    if not topic_arn:
        log.info(
            "SNS report topic already absent."
        )
        return

    aws.sns.delete_topic(
        TopicArn=topic_arn
    )

    log.info(
        "Deleted SNS report topic %s.",
        topic_arn,
    )
