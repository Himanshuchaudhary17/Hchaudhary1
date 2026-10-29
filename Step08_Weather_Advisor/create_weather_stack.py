"""Create the Weather Advisor application stack."""

from __future__ import annotations

import logging

from stack.config import Settings
from stack.runner import create_stack


def main() -> None:
    """Create the application stack and print useful outputs."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    settings = Settings.from_file()

    outputs = create_stack(settings)

    print()
    print("Weather Advisor stack created.")
    print(f"ALB DNS: {outputs.alb_dns_name}")
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
