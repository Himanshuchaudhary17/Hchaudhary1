"""Create the Weather Advisor PostgreSQL database."""

from __future__ import annotations

from pathlib import Path

from stack.clients import AwsClients
from stack.config import Settings
from stack.database import (
    ensure_database,
    ensure_db_password,
    ensure_db_security_group,
    ensure_db_subnet_group,
    find_default_vpc_and_subnets,
)


def main() -> None:
    settings = Settings.from_file()
    aws = AwsClients.create(settings.region)

    print("== 1. Default VPC and subnets ==")
    vpc_id, subnet_a, subnet_b = find_default_vpc_and_subnets(settings, aws)

    print("== 2. Database security group ==")
    db_sg_id = ensure_db_security_group(settings, aws, vpc_id)

    print("== 3. DB subnet group ==")
    ensure_db_subnet_group(settings, aws, subnet_a, subnet_b)

    print("== 4. Database password in SSM ==")
    password = ensure_db_password(settings, aws)

    print("== 5. PostgreSQL instance ==")
    db_host = ensure_database(settings, aws, db_sg_id, password)

    Path("db_outputs.env").write_text(
        f"DB_HOST={db_host}\n"
        f"DB_SECURITY_GROUP_ID={db_sg_id}\n"
    )

    print()
    print(f"Done. Database endpoint: {db_host}")
    print("Automated backups are OFF.")
    print("Database is private, encrypted, and single-AZ.")


if __name__ == "__main__":
    main()
