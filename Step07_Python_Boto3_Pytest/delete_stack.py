#!/usr/bin/env python3
"""Delete the lab stack."""
import logging

from stack.config import Settings
from stack.runner import delete_stack


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    settings = Settings.from_file(".env")
    delete_stack(settings)

    print()
    print("Stack deletion complete.")


if __name__ == "__main__":
    main()
