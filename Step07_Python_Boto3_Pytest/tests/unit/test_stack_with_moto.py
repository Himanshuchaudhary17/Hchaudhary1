from stack.network import (
    default_vpc_id,
    ensure_alb_security_group,
    find_security_group,
)
from stack.storage import (
    delete_bucket,
    delete_role_and_profile,
    ensure_bucket,
    ensure_role_and_profile,
)


def test_bucket_creation_is_idempotent(moto_aws, fake_settings):
    ensure_bucket(moto_aws, fake_settings)
    ensure_bucket(moto_aws, fake_settings)

    buckets = [
        b["Name"]
        for b in moto_aws.s3.list_buckets()["Buckets"]
    ]

    assert fake_settings.bucket_name in buckets


def test_bucket_public_access_is_blocked(moto_aws, fake_settings):
    ensure_bucket(moto_aws, fake_settings)

    config = moto_aws.s3.get_public_access_block(
        Bucket=fake_settings.bucket_name
    )["PublicAccessBlockConfiguration"]

    assert config["BlockPublicAcls"] is True
    assert config["IgnorePublicAcls"] is True
    assert config["BlockPublicPolicy"] is True
    assert config["RestrictPublicBuckets"] is True


def test_role_and_profile_creation_is_idempotent(
    moto_aws,
    fake_settings,
):
    tier = fake_settings.uploader

    ensure_role_and_profile(moto_aws, fake_settings, tier)
    ensure_role_and_profile(moto_aws, fake_settings, tier)

    role = moto_aws.iam.get_role(
        RoleName=tier.role_name
    )["Role"]

    profile = moto_aws.iam.get_instance_profile(
        InstanceProfileName=tier.profile_name
    )["InstanceProfile"]

    assert role["RoleName"] == tier.role_name
    assert tier.role_name in [
        r["RoleName"]
        for r in profile["Roles"]
    ]


def test_alb_security_group_creation_is_idempotent(
    moto_aws,
    fake_settings,
):
    vpc_id = default_vpc_id(moto_aws)

    first = ensure_alb_security_group(
        moto_aws,
        fake_settings,
        vpc_id,
    )

    second = ensure_alb_security_group(
        moto_aws,
        fake_settings,
        vpc_id,
    )

    assert first == second


def test_find_security_group_returns_created_group(
    moto_aws,
    fake_settings,
):
    vpc_id = default_vpc_id(moto_aws)

    created = ensure_alb_security_group(
        moto_aws,
        fake_settings,
        vpc_id,
    )

    found = find_security_group(
        moto_aws,
        fake_settings.alb_sg_name,
        vpc_id,
    )

    assert found == created


def test_delete_role_and_profile_is_repeatable(
    moto_aws,
    fake_settings,
):
    tier = fake_settings.viewer

    ensure_role_and_profile(moto_aws, fake_settings, tier)

    delete_role_and_profile(moto_aws, tier)
    delete_role_and_profile(moto_aws, tier)


def test_delete_bucket_is_repeatable(
    moto_aws,
    fake_settings,
):
    ensure_bucket(moto_aws, fake_settings)

    delete_bucket(moto_aws, fake_settings)
    delete_bucket(moto_aws, fake_settings)
