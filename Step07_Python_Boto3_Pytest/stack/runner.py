"""High-level create/delete orchestration for the whole stack."""
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
from .compute import delete_launch_template, ensure_launch_template
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
from .scaling import delete_asg, ensure_asg
from .storage import (
    delete_bucket,
    delete_role_and_profile,
    ensure_bucket,
    ensure_role_and_profile,
)

log = logging.getLogger("stack")


def create_stack(settings: Settings) -> StackOutputs:
    aws = AwsClients.create(settings.region)

    vpc_id = default_vpc_id(aws)
    subnet_a = subnet_in_az(aws, vpc_id, settings.az_a)
    subnet_b = subnet_in_az(aws, vpc_id, settings.az_b)

    ensure_bucket(aws, settings)

    for tier in settings.tiers:
        ensure_role_and_profile(aws, settings, tier)

    log.info("Waiting 15s for IAM propagation...")
    time.sleep(15)

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

    tg_arns = {}
    lt_versions = {}

    for tier in settings.tiers:
        tg_arns[tier.name] = ensure_target_group(
            aws,
            settings,
            tier,
            vpc_id,
        )

        lt_versions[tier.name] = ensure_launch_template(
            aws,
            settings,
            tier,
        )

    lb = ensure_load_balancer(
        aws,
        settings,
        subnet_a,
        subnet_b,
        alb_sg_id,
    )

    for tier in settings.tiers:
        ensure_listener(
            aws,
            lb["LoadBalancerArn"],
            tier,
            tg_arns[tier.name],
        )

        ensure_asg(
            aws,
            settings,
            tier,
            tg_arns[tier.name],
            lt_versions[tier.name],
            subnet_a,
            subnet_b,
        )

    outputs = StackOutputs(
        vpc_id=vpc_id,
        subnet_a=subnet_a,
        subnet_b=subnet_b,
        alb_security_group_id=alb_sg_id,
        alb_arn=lb["LoadBalancerArn"],
        alb_dns_name=lb["DNSName"],
        uploader_tg_arn=tg_arns["uploader"],
        viewer_tg_arn=tg_arns["viewer"],
    )

    outputs.save()
    return outputs


def delete_stack(settings: Settings) -> None:
    aws = AwsClients.create(settings.region)

    vpc_id = default_vpc_id(aws)

    alb_sg_id = find_security_group(
        aws,
        settings.alb_sg_name,
        vpc_id,
    )

    for tier in settings.tiers:
        delete_asg(aws, tier)

    delete_load_balancer(aws, settings)

    for tier in settings.tiers:
        delete_target_group(aws, tier)

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

    for tier in settings.tiers:
        delete_launch_template(aws, tier)

    for tier in settings.tiers:
        delete_role_and_profile(aws, tier)

    delete_bucket(aws, settings)

    StackOutputs.remove(Path("."))
