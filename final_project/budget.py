"""Estimated operating cost for the Weather Advisor final project.

This is a planning estimate, not an AWS invoice.
Prices are intentionally conservative for low classroom traffic.
"""

from __future__ import annotations

import argparse


# Approximate public AWS prices used for planning.
# EC2 t3.micro Linux/Unix: $0.0104 per instance-hour.
EC2_T3_MICRO_HOURLY = 0.0104
EC2_INSTANCE_COUNT = 2

# Application Load Balancer base hourly charge.
ALB_HOURLY = 0.0225

# Very small classroom workload assumption:
# approximately 0.10 LCU average.
ALB_LCU_PRICE = 0.008
ESTIMATED_ALB_LCU = 0.10

# Two small gp3 root volumes, estimated at 8 GiB each.
EBS_GB_MONTH = 0.08
EBS_GB_PER_INSTANCE = 8
HOURS_PER_MONTH = 730

# Small allowance for DynamoDB, SNS, logs, and data transfer.
VARIABLE_SERVICES_HOURLY_ALLOWANCE = 0.003


def hourly_estimate() -> dict[str, float]:
    ec2 = (
        EC2_T3_MICRO_HOURLY
        * EC2_INSTANCE_COUNT
    )

    alb_base = ALB_HOURLY

    alb_lcu = (
        ALB_LCU_PRICE
        * ESTIMATED_ALB_LCU
    )

    ebs = (
        EBS_GB_MONTH
        * EBS_GB_PER_INSTANCE
        * EC2_INSTANCE_COUNT
        / HOURS_PER_MONTH
    )

    variable = (
        VARIABLE_SERVICES_HOURLY_ALLOWANCE
    )

    total = (
        ec2
        + alb_base
        + alb_lcu
        + ebs
        + variable
    )

    return {
        "EC2": ec2,
        "ALB base": alb_base,
        "ALB estimated LCU": alb_lcu,
        "EBS": ebs,
        "DynamoDB/SNS/logs/data": variable,
        "Total": total,
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--hours",
        type=float,
        default=24,
        help="Number of stack-running hours to estimate.",
    )

    args = parser.parse_args()

    costs = hourly_estimate()

    print("Weather Advisor Cost Estimate")
    print("=" * 36)

    for name, value in costs.items():
        if name != "Total":
            print(
                f"{name:<24} "
                f"${value:.4f}/hour"
            )

    hourly = costs["Total"]
    total = hourly * args.hours

    print("-" * 36)
    print(
        f"{'Estimated hourly total':<24} "
        f"${hourly:.4f}/hour"
    )

    print(
        f"{'Runtime used':<24} "
        f"{args.hours:.1f} hours"
    )

    print(
        f"{'Estimated project cost':<24} "
        f"${total:.2f}"
    )

    print()
    print(
        "Hourly target (< $0.07):",
        "PASS" if hourly < 0.07 else "FAIL",
    )

    print(
        "Project target (< $2.00):",
        "PASS" if total < 2.00 else "FAIL",
    )

    if hourly > 0:
        max_hours = 2.00 / hourly

        print(
            f"Approximate maximum runtime "
            f"before $2: {max_hours:.1f} hours"
        )


if __name__ == "__main__":
    main()
