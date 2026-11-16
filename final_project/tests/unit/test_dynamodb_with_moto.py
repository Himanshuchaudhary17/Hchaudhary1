"""Moto tests for final-project DynamoDB tables."""

from __future__ import annotations

from stack.dynamodb import (
    delete_advisor_table,
    delete_weather_table,
    ensure_advisor_table,
    ensure_weather_table,
)


def test_weather_table_creation_is_idempotent(
    moto_aws,
    fake_settings,
):
    first = ensure_weather_table(
        moto_aws,
        fake_settings,
    )

    second = ensure_weather_table(
        moto_aws,
        fake_settings,
    )

    assert first == second

    table = (
        moto_aws.dynamodb
        .describe_table(
            TableName=
                fake_settings
                .weather_table_name
        )[
            "Table"
        ]
    )

    assert (
        table[
            "BillingModeSummary"
        ][
            "BillingMode"
        ]
        == "PAY_PER_REQUEST"
    )


def test_advisor_table_creation_is_idempotent(
    moto_aws,
    fake_settings,
):
    first = ensure_advisor_table(
        moto_aws,
        fake_settings,
    )

    second = ensure_advisor_table(
        moto_aws,
        fake_settings,
    )

    assert first == second


def test_tables_have_ttl_enabled(
    moto_aws,
    fake_settings,
):
    ensure_weather_table(
        moto_aws,
        fake_settings,
    )

    ensure_advisor_table(
        moto_aws,
        fake_settings,
    )

    for table_name in (
        fake_settings
        .weather_table_name,

        fake_settings
        .advisor_table_name,
    ):
        ttl = (
            moto_aws.dynamodb
            .describe_time_to_live(
                TableName=
                    table_name
            )[
                "TimeToLiveDescription"
            ]
        )

        assert (
            ttl[
                "AttributeName"
            ]
            == "expiresAt"
        )


def test_delete_tables_is_repeatable(
    moto_aws,
    fake_settings,
):
    ensure_weather_table(
        moto_aws,
        fake_settings,
    )

    ensure_advisor_table(
        moto_aws,
        fake_settings,
    )

    delete_weather_table(
        moto_aws,
        fake_settings,
    )

    delete_advisor_table(
        moto_aws,
        fake_settings,
    )

    delete_weather_table(
        moto_aws,
        fake_settings,
    )

    delete_advisor_table(
        moto_aws,
        fake_settings,
    )
