from stack.network import (
    default_vpc_id,
    ensure_alb_security_group,
    find_security_group,
)
from stack.storage import (
    delete_role_and_profile,
    ensure_role_and_profile,
)


def test_role_and_profile_creation_is_idempotent(
    moto_aws,
    fake_settings,
):
    account_id = (
        moto_aws.sts.get_caller_identity()[
            "Account"
        ]
    )

    tier = fake_settings.weather

    ensure_role_and_profile(
        moto_aws,
        fake_settings,
        tier,
        account_id,
    )

    ensure_role_and_profile(
        moto_aws,
        fake_settings,
        tier,
        account_id,
    )

    role = moto_aws.iam.get_role(
        RoleName=tier.role_name
    )["Role"]

    profile = (
        moto_aws.iam.get_instance_profile(
            InstanceProfileName=tier.profile_name
        )["InstanceProfile"]
    )

    assert role["RoleName"] == tier.role_name

    assert tier.role_name in [
        role["RoleName"]
        for role in profile["Roles"]
    ]


def test_weather_role_policy_points_to_db_secret(
    moto_aws,
    fake_settings,
):
    account_id = (
        moto_aws.sts.get_caller_identity()[
            "Account"
        ]
    )

    tier = fake_settings.weather

    ensure_role_and_profile(
        moto_aws,
        fake_settings,
        tier,
        account_id,
    )

    policy = moto_aws.iam.get_role_policy(
        RoleName=tier.role_name,
        PolicyName=tier.policy_name,
    )["PolicyDocument"]

    resource = (
        policy["Statement"][0][
            "Resource"
        ]
    )

    assert resource.endswith(
        "parameter/itmo-444-544/db-password"
    )


def test_advisor_role_policy_points_to_gemini_secret(
    moto_aws,
    fake_settings,
):
    account_id = (
        moto_aws.sts.get_caller_identity()[
            "Account"
        ]
    )

    tier = fake_settings.advisor

    ensure_role_and_profile(
        moto_aws,
        fake_settings,
        tier,
        account_id,
    )

    policy = moto_aws.iam.get_role_policy(
        RoleName=tier.role_name,
        PolicyName=tier.policy_name,
    )["PolicyDocument"]

    resource = (
        policy["Statement"][0][
            "Resource"
        ]
    )

    assert resource.endswith(
        "parameter/itmo-444-544/gemini-api-key"
    )


def test_alb_security_group_creation_is_idempotent(
    moto_aws,
    fake_settings,
):
    vpc_id = default_vpc_id(
        moto_aws
    )

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
    vpc_id = default_vpc_id(
        moto_aws
    )

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


def test_delete_weather_role_is_repeatable(
    moto_aws,
    fake_settings,
):
    account_id = (
        moto_aws.sts.get_caller_identity()[
            "Account"
        ]
    )

    tier = fake_settings.weather

    ensure_role_and_profile(
        moto_aws,
        fake_settings,
        tier,
        account_id,
    )

    delete_role_and_profile(
        moto_aws,
        tier,
    )

    delete_role_and_profile(
        moto_aws,
        tier,
    )
