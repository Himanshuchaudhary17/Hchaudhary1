"""One place that builds the boto3 clients the stack needs."""

from __future__ import annotations

from dataclasses import dataclass

import boto3


@dataclass
class AwsClients:
    """AWS service clients used by the stack."""

    s3: object
    iam: object
    ec2: object
    elbv2: object
    autoscaling: object
    rds: object
    ssm: object
    sts: object

    @classmethod
    def create(
        cls,
        region: str,
    ) -> "AwsClients":
        """Create all required boto3 clients."""

        session = boto3.session.Session(
            region_name=region
        )

        return cls(
            s3=session.client("s3"),
            iam=session.client("iam"),
            ec2=session.client("ec2"),
            elbv2=session.client("elbv2"),
            autoscaling=session.client(
                "autoscaling"
            ),
            rds=session.client("rds"),
            ssm=session.client("ssm"),
            sts=session.client("sts"),
        )
