"""High-level create/delete orchestration for the Weather Advisor stack."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from .balancer import (
    delete_load_balancer,
    delete_target_group,
    ensure_listener,
    ensure_load_balancer,
    ensure_target_group,
)
from .clients import AwsClients
from .compute import (
    delete_launch_template,
    ensure_launch_template,
)
from .config import Settings
from .dynamodb import (
    delete_advisor_table,
    delete_weather_table,
    ensure_advisor_table,
    ensure_weather_table,
)
from .messaging import (
    delete_report_topic,
    ensure_report_topic,
)
from .network import (
    default_vpc_id,
    delete_alb_security_group,
    ensure_alb_security_group,
    find_security_group,
    restore_app_security_group,
    restrict_app_security_group,
    subnet_in_az,
)
from .outputs import StackOutputs
from .scaling import (
    delete_asg,
    ensure_asg,
)
from .storage import (
    delete_role_and_profile,
    ensure_role_and_profile,
)


log = logging.getLogger("stack")


def create_stack(
    settings: Settings,
) -> StackOutputs:
    """Create the Weather Advisor final-project stack."""

    aws = AwsClients.create(
        settings.region
    )

    account_id = (
        aws.sts.get_caller_identity()[
            "Account"
        ]
    )

    vpc_id = default_vpc_id(
        aws
    )

    subnet_a = subnet_in_az(
        aws,
        vpc_id,
        settings.az_a,
    )

    subnet_b = subnet_in_az(
        aws,
        vpc_id,
        settings.az_b,
    )

    log.info(
        "Using VPC %s",
        vpc_id,
    )

    # -------------------------------------------------
    # DynamoDB
    # -------------------------------------------------

    ensure_weather_table(
        aws,
        settings,
    )

    ensure_advisor_table(
        aws,
        settings,
    )

    log.info(
        "Weather cache table is ready: %s",
        settings.weather_table_name,
    )

    log.info(
        "Advisor state table is ready: %s",
        settings.advisor_table_name,
    )

    # -------------------------------------------------
    # SNS
    # -------------------------------------------------

    topic_arn = ensure_report_topic(
        aws,
        settings,
    )

    log.info(
        "SNS report topic is ready: %s",
        topic_arn,
    )

    # -------------------------------------------------
    # IAM
    # -------------------------------------------------

    for tier in settings.tiers:
        ensure_role_and_profile(
            aws,
            settings,
            tier,
            account_id,
        )

    log.info(
        "Waiting 15 seconds for IAM propagation..."
    )

    time.sleep(15)

    # -------------------------------------------------
    # Security groups
    # -------------------------------------------------

    alb_sg_id = ensure_alb_security_group(
        aws,
        settings,
        vpc_id,
    )

    restrict_app_security_group(
        aws,
        settings,
        alb_sg_id,
    )

    # -------------------------------------------------
    # Target groups
    # -------------------------------------------------

    tg_arns: dict[str, str] = {}

    for tier in settings.tiers:
        tg_arns[tier.name] = (
            ensure_target_group(
                aws,
                settings,
                tier,
                vpc_id,
            )
        )

    # -------------------------------------------------
    # Load balancer
    # -------------------------------------------------

    lb = ensure_load_balancer(
        aws,
        settings,
        subnet_a,
        subnet_b,
        alb_sg_id,
    )

    alb_dns_name = lb[
        "DNSName"
    ]

    log.info(
        "ALB DNS name: %s",
        alb_dns_name,
    )

    # -------------------------------------------------
    # Listeners
    # -------------------------------------------------

    for tier in settings.tiers:
        ensure_listener(
            aws,
            lb[
                "LoadBalancerArn"
            ],
            tier,
            tg_arns[
                tier.name
            ],
        )

    # -------------------------------------------------
    # Launch templates
    # -------------------------------------------------

    lt_versions: dict[str, int] = {}

    lt_versions[
        "weather"
    ] = ensure_launch_template(
        aws,
        settings,
        settings.weather,
    )

    lt_versions[
        "advisor"
    ] = ensure_launch_template(
        aws,
        settings,
        settings.advisor,
        alb_dns_name=(
            alb_dns_name
        ),
        sns_topic_arn=(
            topic_arn
        ),
    )

    # -------------------------------------------------
    # Auto Scaling Groups
    # -------------------------------------------------

    for tier in settings.tiers:
        ensure_asg(
            aws,
            settings,
            tier,
            tg_arns[
                tier.name
            ],
            lt_versions[
                tier.name
            ],
            subnet_a,
            subnet_b,
        )

    # -------------------------------------------------
    # Save outputs
    # -------------------------------------------------

    outputs = StackOutputs(
        vpc_id=vpc_id,
        subnet_a=subnet_a,
        subnet_b=subnet_b,

        alb_security_group_id=(
            alb_sg_id
        ),

        alb_arn=(
            lb[
                "LoadBalancerArn"
            ]
        ),

        alb_dns_name=(
            alb_dns_name
        ),

        weather_tg_arn=(
            tg_arns[
                "weather"
            ]
        ),

        advisor_tg_arn=(
            tg_arns[
                "advisor"
            ]
        ),

        weather_table_name=(
            settings.weather_table_name
        ),

        advisor_table_name=(
            settings.advisor_table_name
        ),

        sns_topic_arn=(
            topic_arn
        ),
    )

    outputs.save()

    log.info(
        "Weather Advisor stack creation complete."
    )

    return outputs


def delete_stack(
    settings: Settings,
) -> None:
    """Delete the final-project application stack."""

    aws = AwsClients.create(
        settings.region
    )

    vpc_id = default_vpc_id(
        aws
    )

    alb_sg_id = find_security_group(
        aws,
        settings.alb_sg_name,
        vpc_id,
    )

    # -------------------------------------------------
    # Auto Scaling Groups
    # -------------------------------------------------

    for tier in settings.tiers:
        delete_asg(
            aws,
            tier,
        )

    # -------------------------------------------------
    # Load balancer
    # -------------------------------------------------

    delete_load_balancer(
        aws,
        settings,
    )

    # -------------------------------------------------
    # Target groups
    # -------------------------------------------------

    for tier in settings.tiers:
        delete_target_group(
            aws,
            tier,
        )

    # -------------------------------------------------
    # Security groups
    # -------------------------------------------------

    restore_app_security_group(
        aws,
        settings,
        alb_sg_id,
    )

    if alb_sg_id:
        delete_alb_security_group(
            aws,
            alb_sg_id,
        )

    # -------------------------------------------------
    # Launch templates
    # -------------------------------------------------

    for tier in settings.tiers:
        delete_launch_template(
            aws,
            tier,
        )

    # -------------------------------------------------
    # IAM
    # -------------------------------------------------

    for tier in settings.tiers:
        delete_role_and_profile(
            aws,
            tier,
        )

    # -------------------------------------------------
    # SNS
    # -------------------------------------------------

    delete_report_topic(
        aws,
        settings,
    )

    # -------------------------------------------------
    # DynamoDB
    # -------------------------------------------------

    delete_advisor_table(
        aws,
        settings,
    )

    delete_weather_table(
        aws,
        settings,
    )

    # -------------------------------------------------
    # Gemini secret
    # -------------------------------------------------

    try:
        aws.ssm.delete_parameter(
            Name=settings.gemini_param_name
        )

        log.info(
            "Deleted Gemini SSM parameter %s",
            settings.gemini_param_name,
        )

    except aws.ssm.exceptions.ParameterNotFound:
        log.info(
            "Gemini SSM parameter already absent."
        )

    # -------------------------------------------------
    # Local generated outputs
    # -------------------------------------------------

    StackOutputs.remove(
        Path(".")
    )

    log.info(
        "Weather Advisor stack deletion complete."
    )
