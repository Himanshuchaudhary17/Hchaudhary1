"""Delete the Weather Advisor PostgreSQL database and related resources."""

from __future__ import annotations

from pathlib import Path

from stack.clients import AwsClients
from stack.config import Settings
from stack.database import delete_database_resources


def main() -> None:
    settings = Settings.from_file()
    aws = AwsClients.create(settings.region)

    print("== Deleting Weather Advisor database resources ==")

    delete_database_resources(settings, aws)

    Path("db_outputs.env").unlink(missing_ok=True)

    print("Database resources removed.")
    print("No final snapshot was kept.")
    print("Automated backups were deleted.")


if __name__ == "__main__":
    main()
