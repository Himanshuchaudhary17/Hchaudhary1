#!/usr/bin/env python3
"""Create or update the lab stack."""
import logging

from stack.config import Settings
from stack.runner import create_stack


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    settings = Settings.from_file(".env")
    outputs = create_stack(settings)

    print()
    print("Stack creation complete.")
    print(f"Uploader URL: http://{outputs.alb_dns_name}:{settings.uploader.listener_port}")
    print(f"Viewer URL:   http://{outputs.alb_dns_name}:{settings.viewer.listener_port}")


if __name__ == "__main__":
    main()
