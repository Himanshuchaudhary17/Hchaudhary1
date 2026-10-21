"""Auto Scaling Groups for the uploader and viewer tiers."""
from __future__ import annotations

import logging

from botocore.exceptions import ClientError

from .clients import AwsClients
from .config import Settings, Tier
from .util import error_code

log = logging.getLogger("stack")


def find_asg(aws: AwsClients, name: str) -> dict | None:
    groups = aws.autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[name]
    )["AutoScalingGroups"]

    return groups[0] if groups else None


def ensure_asg(
    aws: AwsClients,
    settings: Settings,
    tier: Tier,
    target_group_arn: str,
    launch_template_version: int,
    subnet_a: str,
    subnet_b: str,
) -> None:
    existing = find_asg(aws, tier.asg_name)

    launch_template = {
        "LaunchTemplateName": tier.lt_name,
        "Version": str(launch_template_version),
    }

    if existing:
        aws.autoscaling.update_auto_scaling_group(
            AutoScalingGroupName=tier.asg_name,
            LaunchTemplate=launch_template,
            MinSize=1,
            MaxSize=1,
            DesiredCapacity=1,
            VPCZoneIdentifier=f"{subnet_a},{subnet_b}",
        )

        current_tgs = existing.get("TargetGroupARNs", [])
        if target_group_arn not in current_tgs:
            aws.autoscaling.attach_load_balancer_target_groups(
                AutoScalingGroupName=tier.asg_name,
                TargetGroupARNs=[target_group_arn],
            )

        log.info("Updated Auto Scaling Group %s", tier.asg_name)
        return

    aws.autoscaling.create_auto_scaling_group(
        AutoScalingGroupName=tier.asg_name,
        LaunchTemplate=launch_template,
        MinSize=1,
        MaxSize=1,
        DesiredCapacity=1,
        VPCZoneIdentifier=f"{subnet_a},{subnet_b}",
        TargetGroupARNs=[target_group_arn],
        HealthCheckType="ELB",
        HealthCheckGracePeriod=60,
        Tags=[{
            "Key": "Name",
            "Value": f"{tier.name}-asg-instance",
            "PropagateAtLaunch": True,
        }],
    )

    log.info("Created Auto Scaling Group %s", tier.asg_name)


def delete_asg(aws: AwsClients, tier: Tier) -> None:
    if not find_asg(aws, tier.asg_name):
        return

    try:
        aws.autoscaling.delete_auto_scaling_group(
            AutoScalingGroupName=tier.asg_name,
            ForceDelete=True,
        )
        log.info("Deleted Auto Scaling Group %s", tier.asg_name)
    except ClientError as err:
        if error_code(err) != "ValidationError":
            raise
