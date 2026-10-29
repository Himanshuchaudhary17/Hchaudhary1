"""Moto unit tests for the Weather Advisor PostgreSQL infrastructure."""

from __future__ import annotations

from dataclasses import replace

import pytest

import stack.database as database
from stack.database import (
    delete_database_resources,
    ensure_database,
    ensure_db_password,
    ensure_db_security_group,
    ensure_db_subnet_group,
)


def make_database_network(fake_settings, moto_aws):
    """Create a moto VPC, app SG and two subnets for database tests."""

    vpc_id = moto_aws.ec2.create_vpc(
        CidrBlock="10.0.0.0/16"
    )["Vpc"]["VpcId"]

    app_sg_id = moto_aws.ec2.create_security_group(
        GroupName="test-app-sg",
        Description="Application instances",
        VpcId=vpc_id,
    )["GroupId"]

    subnet_a = moto_aws.ec2.create_subnet(
        VpcId=vpc_id,
        CidrBlock="10.0.1.0/24",
        AvailabilityZone=fake_settings.az_a,
    )["Subnet"]["SubnetId"]

    subnet_b = moto_aws.ec2.create_subnet(
        VpcId=vpc_id,
        CidrBlock="10.0.2.0/24",
        AvailabilityZone=fake_settings.az_b,
    )["Subnet"]["SubnetId"]

    settings = replace(
        fake_settings,
        app_sg_id=app_sg_id,
    )

    return settings, vpc_id, subnet_a, subnet_b


def create_database_stack(fake_settings, moto_aws):
    """Create all database resources needed by a unit test."""

    settings, vpc_id, subnet_a, subnet_b = make_database_network(
        fake_settings,
        moto_aws,
    )

    db_sg_id = ensure_db_security_group(
        settings,
        moto_aws,
        vpc_id,
    )

    ensure_db_subnet_group(
        settings,
        moto_aws,
        subnet_a,
        subnet_b,
    )

    password = ensure_db_password(
        settings,
        moto_aws,
    )

    host = ensure_database(
        settings,
        moto_aws,
        db_sg_id,
        password,
    )

    return (
        settings,
        vpc_id,
        subnet_a,
        subnet_b,
        db_sg_id,
        password,
        host,
    )


def test_database_has_required_configuration(
    fake_settings,
    moto_aws,
):
    """The RDS instance must match the Graduate Checklist settings."""

    (
        settings,
        _,
        _,
        _,
        _,
        _,
        host,
    ) = create_database_stack(
        fake_settings,
        moto_aws,
    )

    assert host

    db = moto_aws.rds.describe_db_instances(
        DBInstanceIdentifier=settings.db_instance_id
    )["DBInstances"][0]

    assert db["DBInstanceClass"] == "db.t4g.micro"
    assert db["Engine"] == "postgres"
    assert db["AllocatedStorage"] == 20
    assert db["BackupRetentionPeriod"] == 0
    assert db["MultiAZ"] is False
    assert db["PubliclyAccessible"] is False
    assert db["StorageEncrypted"] is True


def test_database_security_group_allows_only_app_sg(
    fake_settings,
    moto_aws,
):
    """PostgreSQL 5432 must be allowed from the app SG and no CIDR."""

    settings, vpc_id, _, _ = make_database_network(
        fake_settings,
        moto_aws,
    )

    db_sg_id = ensure_db_security_group(
        settings,
        moto_aws,
        vpc_id,
    )

    group = moto_aws.ec2.describe_security_groups(
        GroupIds=[db_sg_id]
    )["SecurityGroups"][0]

    permissions = [
        rule
        for rule in group["IpPermissions"]
        if rule.get("FromPort") == 5432
        and rule.get("ToPort") == 5432
    ]

    assert len(permissions) == 1

    rule = permissions[0]

    assert rule["IpProtocol"] == "tcp"

    source_group_ids = {
        pair["GroupId"]
        for pair in rule.get("UserIdGroupPairs", [])
    }

    assert source_group_ids == {
        settings.app_sg_id
    }

    assert rule.get("IpRanges", []) == []
    assert rule.get("Ipv6Ranges", []) == []


def test_database_create_functions_are_idempotent(
    fake_settings,
    moto_aws,
):
    """Running database create functions twice must not create duplicates."""

    settings, vpc_id, subnet_a, subnet_b = make_database_network(
        fake_settings,
        moto_aws,
    )

    first_sg = ensure_db_security_group(
        settings,
        moto_aws,
        vpc_id,
    )

    second_sg = ensure_db_security_group(
        settings,
        moto_aws,
        vpc_id,
    )

    assert first_sg == second_sg

    ensure_db_subnet_group(
        settings,
        moto_aws,
        subnet_a,
        subnet_b,
    )

    ensure_db_subnet_group(
        settings,
        moto_aws,
        subnet_a,
        subnet_b,
    )

    first_password = ensure_db_password(
        settings,
        moto_aws,
    )

    second_password = ensure_db_password(
        settings,
        moto_aws,
    )

    assert first_password == second_password

    first_host = ensure_database(
        settings,
        moto_aws,
        first_sg,
        first_password,
    )

    second_host = ensure_database(
        settings,
        moto_aws,
        first_sg,
        first_password,
    )

    assert first_host == second_host

    groups = moto_aws.ec2.describe_security_groups(
        Filters=[
            {
                "Name": "group-name",
                "Values": [settings.db_sg_name],
            }
        ]
    )["SecurityGroups"]

    assert len(groups) == 1

    subnet_groups = moto_aws.rds.describe_db_subnet_groups(
        DBSubnetGroupName=settings.db_subnet_group_name
    )["DBSubnetGroups"]

    assert len(subnet_groups) == 1

    dbs = moto_aws.rds.describe_db_instances(
        DBInstanceIdentifier=settings.db_instance_id
    )["DBInstances"]

    assert len(dbs) == 1


def test_create_then_delete_leaves_no_database_or_password(
    fake_settings,
    moto_aws,
    monkeypatch,
):
    """Create then delete must remove DB, snapshots and password parameter."""

    (
        settings,
        vpc_id,
        subnet_a,
        subnet_b,
        _,
        _,
        _,
    ) = create_database_stack(
        fake_settings,
        moto_aws,
    )

    monkeypatch.setattr(
        database,
        "find_default_vpc_and_subnets",
        lambda settings_arg, aws_arg: (
            vpc_id,
            subnet_a,
            subnet_b,
        ),
    )

    delete_database_resources(
        settings,
        moto_aws,
    )

    with pytest.raises(
        moto_aws.rds.exceptions.DBInstanceNotFoundFault
    ):
        moto_aws.rds.describe_db_instances(
            DBInstanceIdentifier=settings.db_instance_id
        )

    snapshots = moto_aws.rds.describe_db_snapshots(
        DBInstanceIdentifier=settings.db_instance_id
    )["DBSnapshots"]

    assert snapshots == []

    with pytest.raises(
        moto_aws.ssm.exceptions.ParameterNotFound
    ):
        moto_aws.ssm.get_parameter(
            Name=settings.db_password_param
        )
