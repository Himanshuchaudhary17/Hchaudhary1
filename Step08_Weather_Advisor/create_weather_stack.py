"""Create the Weather Advisor application stack."""

from __future__ import annotations

import getpass
import logging

from botocore.exceptions import ClientError

from stack.clients import AwsClients
from stack.config import Settings
from stack.runner import create_stack


def ensure_gemini_key(
    settings: Settings,
    aws: AwsClients,
) -> None:
    """Store the Gemini API key in SSM only when it is missing."""

    try:
        aws.ssm.get_parameter(
            Name=settings.gemini_param_name,
            WithDecryption=False,
        )

        logging.info(
            "Gemini API key parameter already exists."
        )

    except ClientError as err:
        if (
            err.response["Error"]["Code"]
            != "ParameterNotFound"
        ):
            raise

        api_key = getpass.getpass(
            "Gemini API key: "
        ).strip()

        if not api_key:
            raise ValueError(
                "Gemini API key cannot be empty."
            )

        aws.ssm.put_parameter(
            Name=settings.gemini_param_name,
            Type="SecureString",
            Value=api_key,
            Overwrite=False,
        )

        logging.info(
            "Gemini API key stored securely in SSM."
        )


def main() -> None:
    """Create the application stack and print useful outputs."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    settings = Settings.from_file()

    aws = AwsClients.create(
        settings.region
    )

    ensure_gemini_key(
        settings,
        aws,
    )

    outputs = create_stack(
        settings
    )

    print()
    print(
        "Weather Advisor stack created."
    )

    print(
        f"ALB DNS: {outputs.alb_dns_name}"
    )

    print(
        "Weather URL: "
        f"http://{outputs.alb_dns_name}:"
        f"{settings.weather.listener_port}"
    )

    print(
        "Advisor URL: "
        f"http://{outputs.alb_dns_name}:"
        f"{settings.advisor.listener_port}"
    )


if __name__ == "__main__":
    main()
