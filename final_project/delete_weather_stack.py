"""Delete all Weather Advisor final-project AWS resources."""

from __future__ import annotations

import logging

from stack.config import Settings
from stack.runner import delete_stack


def main() -> None:
    """Delete the complete Weather Advisor stack."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    settings = Settings.from_file(
        ".env"
    )

    delete_stack(
        settings
    )

    print()
    print(
        "Weather Advisor final-project stack deleted."
    )


if __name__ == "__main__":
    main()
