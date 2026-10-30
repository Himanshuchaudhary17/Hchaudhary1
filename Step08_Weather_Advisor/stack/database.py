"""RDS PostgreSQL resources for the Weather Advisor lab."""

from __future__ import annotations

import secrets
from botocore.exceptions import ClientError

from stack.config import Settings
from stack.clients import AwsClients


def find_default_vpc_and_subnets(settings: Settings, aws: AwsClients):
    """Return default VPC ID and one subnet in each configured AZ."""

    vpcs = aws.ec2.describe_vpcs(
        Filters=[{"Name": "isDefault", "Values": ["true"]}]
    )["Vpcs"]

    vpc_id = vpcs[0]["VpcId"]

    subnet_a = aws.ec2.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "availability-zone", "Values": [settings.az_a]},
        ]
    )["Subnets"][0]["SubnetId"]

    subnet_b = aws.ec2.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "availability-zone", "Values": [settings.az_b]},
        ]
    )["Subnets"][0]["SubnetId"]

    return vpc_id, subnet_a, subnet_b


def ensure_db_security_group(
    settings: Settings,
    aws: AwsClients,
    vpc_id: str,
) -> str:
    """Create or find the DB security group."""

    groups = aws.ec2.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": [settings.db_sg_name]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
    )["SecurityGroups"]

    if groups:
        return groups[0]["GroupId"]

    sg_id = aws.ec2.create_security_group(
        GroupName=settings.db_sg_name,
        Description="PostgreSQL access from the lab app instances only",
        VpcId=vpc_id,
    )["GroupId"]

    aws.ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": settings.db_port,
                "ToPort": settings.db_port,
                "UserIdGroupPairs": [
                    {"GroupId": settings.app_sg_id}
                ],
            }
        ],
    )

    return sg_id


def ensure_db_subnet_group(
    settings: Settings,
    aws: AwsClients,
    subnet_a: str,
    subnet_b: str,
) -> None:
    """Create the RDS DB subnet group if needed."""

    try:
        aws.rds.create_db_subnet_group(
            DBSubnetGroupName=settings.db_subnet_group_name,
            DBSubnetGroupDescription="Lab subnets for the weather database",
            SubnetIds=[subnet_a, subnet_b],
        )
    except ClientError as err:
        if err.response["Error"]["Code"] != "DBSubnetGroupAlreadyExists":
            raise


def ensure_db_password(settings: Settings, aws: AwsClients) -> str:
    """Create or return the database password stored in SSM."""

    try:
        out = aws.ssm.get_parameter(
            Name=settings.db_password_param,
            WithDecryption=True,
        )
        return out["Parameter"]["Value"]

    except aws.ssm.exceptions.ParameterNotFound:
        password = secrets.token_hex(16)

        aws.ssm.put_parameter(
            Name=settings.db_password_param,
            Type="SecureString",
            Value=password,
            Overwrite=False,
        )

        return password


def ensure_database(
    settings: Settings,
    aws: AwsClients,
    db_sg_id: str,
    password: str,
) -> str:
    """Create the PostgreSQL instance if it does not already exist."""

    try:
        out = aws.rds.describe_db_instances(
            DBInstanceIdentifier=settings.db_instance_id
        )

        db = out["DBInstances"][0]

    except ClientError as err:
        if err.response["Error"]["Code"] != "DBInstanceNotFound":
            raise

        aws.rds.create_db_instance(
            DBInstanceIdentifier=settings.db_instance_id,
            DBInstanceClass=settings.db_instance_class,
            Engine="postgres",
            AllocatedStorage=20,
            StorageType="gp2",
            MasterUsername=settings.db_user,
            MasterUserPassword=password,
            DBName=settings.db_name,
            DBSubnetGroupName=settings.db_subnet_group_name,
            VpcSecurityGroupIds=[db_sg_id],
            AvailabilityZone=settings.az_a,
            BackupRetentionPeriod=0,
            MultiAZ=False,
            PubliclyAccessible=False,
            AutoMinorVersionUpgrade=False,
            DeletionProtection=False,
            StorageEncrypted=True,
        )

        waiter = aws.rds.get_waiter("db_instance_available")

        waiter.wait(
            DBInstanceIdentifier=settings.db_instance_id
        )

        db = aws.rds.describe_db_instances(
            DBInstanceIdentifier=settings.db_instance_id
        )["DBInstances"][0]

    return db["Endpoint"]["Address"]


def delete_database_resources(
    settings: Settings,
    aws: AwsClients,
) -> None:
    """Delete DB instance, subnet group, security group and password parameter."""

    try:
        aws.rds.describe_db_instances(
            DBInstanceIdentifier=settings.db_instance_id
        )

        aws.rds.delete_db_instance(
            DBInstanceIdentifier=settings.db_instance_id,
            SkipFinalSnapshot=True,
            DeleteAutomatedBackups=True,
        )

        waiter = aws.rds.get_waiter("db_instance_deleted")

        waiter.wait(
            DBInstanceIdentifier=settings.db_instance_id
        )

    except ClientError as err:
        if err.response["Error"]["Code"] != "DBInstanceNotFound":
            raise

    try:
        aws.rds.delete_db_subnet_group(
            DBSubnetGroupName=settings.db_subnet_group_name
        )
    except ClientError:
        pass

    vpc_id, _, _ = find_default_vpc_and_subnets(settings, aws)

    groups = aws.ec2.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": [settings.db_sg_name]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
    )["SecurityGroups"]

    if groups:
        try:
            aws.ec2.delete_security_group(
                GroupId=groups[0]["GroupId"]
            )
        except ClientError:
            pass

    try:
        aws.ssm.delete_parameter(
            Name=settings.db_password_param
        )
    except ClientError:
        pass
