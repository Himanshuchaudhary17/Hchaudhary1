"""Delete the Weather Advisor application stack."""

from __future__ import annotations

import logging

from stack.config import Settings
from stack.runner import delete_stack


def main() -> None:
    """Delete the application stack."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    settings = Settings.from_file()

    delete_stack(settings)

    print()
    print("Weather Advisor application stack deleted.")
    print(
        "Note: the RDS database is separate. "
        "Run delete_database.py when you are completely finished."
    )


if __name__ == "__main__":
    main()
