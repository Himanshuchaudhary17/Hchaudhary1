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


def database_endpoint(
    aws: AwsClients,
    settings: Settings,
) -> str:
    """Return the endpoint of the existing RDS database."""

    response = aws.rds.describe_db_instances(
        DBInstanceIdentifier=settings.db_instance_id
    )

    instances = response.get(
        "DBInstances",
        [],
    )

    if not instances:
        raise RuntimeError(
            "Weather database does not exist. "
            "Run create_database.py first."
        )

    endpoint = instances[0].get(
        "Endpoint",
        {},
    ).get("Address")

    if not endpoint:
        raise RuntimeError(
            "Database endpoint is not available yet."
        )

    return endpoint


def create_stack(
    settings: Settings,
) -> StackOutputs:
    """Create the Weather Advisor application stack."""

    aws = AwsClients.create(
        settings.region
    )

    # -------------------------------------------------
    # 1. Account, VPC, and subnets
    # -------------------------------------------------

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
    # 2. Existing database endpoint
    # -------------------------------------------------

    db_host = database_endpoint(
        aws,
        settings,
    )

    log.info(
        "Using database endpoint %s",
        db_host,
    )

    # -------------------------------------------------
    # 3. IAM roles and instance profiles
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
    # 4. Security groups
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
    # 5. Target groups
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
    # 6. ALB
    #
    # Important:
    # The ALB exists before launch templates because
    # Advisor user-data needs its DNS name.
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
    # 7. Listeners
    # -------------------------------------------------

    for tier in settings.tiers:
        ensure_listener(
            aws,
            lb["LoadBalancerArn"],
            tier,
            tg_arns[tier.name],
        )

    # -------------------------------------------------
    # 8. Launch templates
    # -------------------------------------------------

    lt_versions: dict[str, int] = {}

    lt_versions["weather"] = (
        ensure_launch_template(
            aws,
            settings,
            settings.weather,
            db_host=db_host,
        )
    )

    lt_versions["advisor"] = (
        ensure_launch_template(
            aws,
            settings,
            settings.advisor,
            alb_dns_name=alb_dns_name,
        )
    )

    # -------------------------------------------------
    # 9. Auto Scaling Groups
    # -------------------------------------------------

    for tier in settings.tiers:
        ensure_asg(
            aws,
            settings,
            tier,
            tg_arns[tier.name],
            lt_versions[tier.name],
            subnet_a,
            subnet_b,
        )

    # -------------------------------------------------
    # 10. Save outputs
    # -------------------------------------------------

    outputs = StackOutputs(
        vpc_id=vpc_id,
        subnet_a=subnet_a,
        subnet_b=subnet_b,
        alb_security_group_id=alb_sg_id,
        alb_arn=lb[
            "LoadBalancerArn"
        ],
        alb_dns_name=alb_dns_name,
        weather_tg_arn=(
            tg_arns["weather"]
        ),
        advisor_tg_arn=(
            tg_arns["advisor"]
        ),
        db_host=db_host,
    )

    outputs.save()

    log.info(
        "Weather Advisor stack creation complete."
    )

    return outputs


def delete_stack(
    settings: Settings,
) -> None:
    """Delete the application stack but leave RDS for separate cleanup."""

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

    # ASGs first so instances stop using
    # load balancer and instance profiles.
    for tier in settings.tiers:
        delete_asg(
            aws,
            tier,
        )

    # Remove ALB.
    delete_load_balancer(
        aws,
        settings,
    )

    # Remove target groups.
    for tier in settings.tiers:
        delete_target_group(
            aws,
            tier,
        )

    # Restore the shared app security group.
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

    # Remove launch templates.
    for tier in settings.tiers:
        delete_launch_template(
            aws,
            tier,
        )

    # Remove IAM roles and profiles.
    for tier in settings.tiers:
        delete_role_and_profile(
            aws,
            tier,
        )

    StackOutputs.remove(
        Path(".")
    )

    log.info(
        "Weather Advisor application stack deleted."
    )
