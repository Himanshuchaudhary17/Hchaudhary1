"""Application Load Balancer, target groups, and listeners."""
from __future__ import annotations

import logging
import time

from .clients import AwsClients
from .config import Settings, Tier
from .util import ignore_errors, retry_on

log = logging.getLogger("stack")


def target_group_health_check(settings: Settings) -> dict:
    return {
        "HealthCheckProtocol": "HTTP",
        "HealthCheckPort": "traffic-port",
        "HealthCheckPath": "/",
        "HealthCheckIntervalSeconds": 10,
        "HealthCheckTimeoutSeconds": 5,
        "HealthyThresholdCount": 2,
        "UnhealthyThresholdCount": 2,
        "Matcher": {"HttpCode": "200"},
    }


def find_target_group(aws: AwsClients, name: str) -> str | None:
    try:
        response = aws.elbv2.describe_target_groups(Names=[name])
    except Exception:
        return None

    groups = response.get("TargetGroups", [])
    return groups[0]["TargetGroupArn"] if groups else None


def ensure_target_group(
    aws: AwsClients,
    settings: Settings,
    tier: Tier,
    vpc_id: str,
) -> str:
    arn = find_target_group(aws, tier.tg_name)

    if arn:
        log.info("Target group %s already exists.", tier.tg_name)
        return arn

    response = aws.elbv2.create_target_group(
        Name=tier.tg_name,
        Protocol="HTTP",
        Port=settings.app_port,
        VpcId=vpc_id,
        TargetType="instance",
        **target_group_health_check(settings),
    )

    arn = response["TargetGroups"][0]["TargetGroupArn"]
    log.info("Created target group %s", tier.tg_name)
    return arn


def find_load_balancer(aws: AwsClients, name: str) -> dict | None:
    try:
        response = aws.elbv2.describe_load_balancers(Names=[name])
    except Exception:
        return None

    lbs = response.get("LoadBalancers", [])
    return lbs[0] if lbs else None


def ensure_load_balancer(
    aws: AwsClients,
    settings: Settings,
    subnet_a: str,
    subnet_b: str,
    alb_sg_id: str,
) -> dict:
    existing = find_load_balancer(aws, settings.alb_name)

    if existing:
        log.info("Load balancer %s already exists.", settings.alb_name)
        return existing

    response = aws.elbv2.create_load_balancer(
        Name=settings.alb_name,
        Subnets=[subnet_a, subnet_b],
        SecurityGroups=[alb_sg_id],
        Scheme="internet-facing",
        Type="application",
        IpAddressType="ipv4",
    )

    lb = response["LoadBalancers"][0]
    log.info("Created load balancer %s", settings.alb_name)
    return lb


def ensure_listener(
    aws: AwsClients,
    lb_arn: str,
    tier: Tier,
    tg_arn: str,
) -> str:
    listeners = aws.elbv2.describe_listeners(
        LoadBalancerArn=lb_arn
    )["Listeners"]

    for listener in listeners:
        if listener["Port"] == tier.listener_port:
            log.info(
                "Listener on port %s already exists.",
                tier.listener_port,
            )
            return listener["ListenerArn"]

    response = aws.elbv2.create_listener(
        LoadBalancerArn=lb_arn,
        Protocol="HTTP",
        Port=tier.listener_port,
        DefaultActions=[{
            "Type": "forward",
            "TargetGroupArn": tg_arn,
        }],
    )

    listener_arn = response["Listeners"][0]["ListenerArn"]
    log.info("Created listener on port %s", tier.listener_port)
    return listener_arn


def delete_load_balancer(
    aws: AwsClients,
    settings: Settings,
    sleep=time.sleep,
) -> None:
    lb = find_load_balancer(aws, settings.alb_name)

    if not lb:
        return

    aws.elbv2.delete_load_balancer(
        LoadBalancerArn=lb["LoadBalancerArn"]
    )

    def wait_until_gone():
        if find_load_balancer(aws, settings.alb_name):
            from botocore.exceptions import ClientError

            raise ClientError(
                {
                    "Error": {
                        "Code": "LoadBalancerStillExists",
                        "Message": "waiting",
                    }
                },
                "DescribeLoadBalancers",
            )

    retry_on(
        {"LoadBalancerStillExists"},
        wait_until_gone,
        attempts=20,
        delay=10,
        sleep=sleep,
    )

    log.info("Deleted load balancer %s", settings.alb_name)


def delete_target_group(
    aws: AwsClients,
    tier: Tier,
    sleep=time.sleep,
) -> None:
    arn = find_target_group(aws, tier.tg_name)

    if not arn:
        return

    with ignore_errors(
        "ResourceInUse",
        "TargetGroupNotFound",
    ):
        retry_on(
            {"ResourceInUse"},
            lambda: aws.elbv2.delete_target_group(
                TargetGroupArn=arn
            ),
            attempts=20,
            delay=10,
            sleep=sleep,
        )

    log.info("Deleted target group %s", tier.tg_name)
