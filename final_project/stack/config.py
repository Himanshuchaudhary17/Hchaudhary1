"""Settings for the Weather Advisor final project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_KEYS = [
    "AWS_REGION",
    "AMI_ID",
    "KEY_NAME",
    "INSTANCE_TYPE",
    "APP_SECURITY_GROUP_ID",
    "AZ_A",
    "AZ_B",

    "APP_PORT",

    "WEATHER_ROLE_NAME",
    "WEATHER_PROFILE_NAME",
    "WEATHER_LT_NAME",
    "WEATHER_TG_NAME",
    "WEATHER_ASG_NAME",
    "WEATHER_LISTENER_PORT",

    "ADVISOR_ROLE_NAME",
    "ADVISOR_PROFILE_NAME",
    "ADVISOR_LT_NAME",
    "ADVISOR_TG_NAME",
    "ADVISOR_ASG_NAME",
    "ADVISOR_LISTENER_PORT",

    "ALB_NAME",
    "ALB_SG_NAME",

    "WEATHER_TABLE_NAME",
    "ADVISOR_TABLE_NAME",
    "CACHE_SECONDS",
    "STALE_CACHE_SECONDS",

    "SNS_TOPIC_NAME",

    "GEMINI_PARAM_NAME",
    "GEMINI_MODEL",
    "KEY_CACHE_SECONDS",

    "CONTACT_EMAIL",
]


class ConfigError(Exception):
    """Raised when required settings are missing or invalid."""


def load_dotenv(
    path: str | Path = ".env",
) -> dict[str, str]:
    """Read KEY=VALUE lines from a .env file."""

    values: dict[str, str] = {}

    for raw in Path(path).read_text().splitlines():
        line = raw.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, _, value = line.partition("=")

        values[key.strip()] = (
            value
            .strip()
            .strip('"')
            .strip("'")
        )

    return values


@dataclass(frozen=True)
class Tier:
    """Configuration for one application tier."""

    name: str
    role_name: str
    profile_name: str
    lt_name: str
    tg_name: str
    asg_name: str
    listener_port: int
    app_dir: Path

    @property
    def policy_name(self) -> str:
        """Return the inline IAM policy name."""

        return f"{self.role_name}-policy"

    @property
    def service_name(self) -> str:
        """Return the systemd service name."""

        return self.name


@dataclass(frozen=True)
class Settings:
    """Final-project configuration."""

    region: str
    ami_id: str
    key_name: str
    instance_type: str

    app_sg_id: str

    az_a: str
    az_b: str

    app_port: int

    alb_name: str
    alb_sg_name: str

    weather_table_name: str
    advisor_table_name: str

    cache_seconds: int
    stale_cache_seconds: int

    sns_topic_name: str

    gemini_param_name: str
    gemini_model: str
    key_cache_seconds: int

    contact_email: str

    weather: Tier
    advisor: Tier

    @property
    def tiers(
        self,
    ) -> tuple[Tier, Tier]:
        """Return both application tiers."""

        return (
            self.weather,
            self.advisor,
        )

    def tier(
        self,
        name: str,
    ) -> Tier:
        """Return a tier by logical name."""

        return {
            "weather": self.weather,
            "advisor": self.advisor,
        }[name]

    @classmethod
    def from_values(
        cls,
        v: dict[str, str],
        base_dir: str | Path = ".",
    ) -> "Settings":
        """Build settings from parsed environment values."""

        missing = [
            key
            for key in REQUIRED_KEYS
            if not v.get(key)
        ]

        if missing:
            raise ConfigError(
                "Missing keys in .env: "
                + ", ".join(missing)
            )

        base = Path(base_dir)

        def tier(
            prefix: str,
        ) -> Tier:
            """Build one tier from prefixed settings."""

            return Tier(
                name=prefix.lower(),

                role_name=v[
                    f"{prefix}_ROLE_NAME"
                ],

                profile_name=v[
                    f"{prefix}_PROFILE_NAME"
                ],

                lt_name=v[
                    f"{prefix}_LT_NAME"
                ],

                tg_name=v[
                    f"{prefix}_TG_NAME"
                ],

                asg_name=v[
                    f"{prefix}_ASG_NAME"
                ],

                listener_port=int(
                    v[
                        f"{prefix}_LISTENER_PORT"
                    ]
                ),

                app_dir=(
                    base
                    / f"{prefix.lower()}-app"
                ),
            )

        return cls(
            region=v[
                "AWS_REGION"
            ],

            ami_id=v[
                "AMI_ID"
            ],

            key_name=v[
                "KEY_NAME"
            ],

            instance_type=v[
                "INSTANCE_TYPE"
            ],

            app_sg_id=v[
                "APP_SECURITY_GROUP_ID"
            ],

            az_a=v[
                "AZ_A"
            ],

            az_b=v[
                "AZ_B"
            ],

            app_port=int(
                v[
                    "APP_PORT"
                ]
            ),

            alb_name=v[
                "ALB_NAME"
            ],

            alb_sg_name=v[
                "ALB_SG_NAME"
            ],

            weather_table_name=v[
                "WEATHER_TABLE_NAME"
            ],

            advisor_table_name=v[
                "ADVISOR_TABLE_NAME"
            ],

            cache_seconds=int(
                v[
                    "CACHE_SECONDS"
                ]
            ),

            stale_cache_seconds=int(
                v[
                    "STALE_CACHE_SECONDS"
                ]
            ),

            sns_topic_name=v[
                "SNS_TOPIC_NAME"
            ],

            gemini_param_name=v[
                "GEMINI_PARAM_NAME"
            ],

            gemini_model=v[
                "GEMINI_MODEL"
            ],

            key_cache_seconds=int(
                v[
                    "KEY_CACHE_SECONDS"
                ]
            ),

            contact_email=v[
                "CONTACT_EMAIL"
            ],

            weather=tier(
                "WEATHER"
            ),

            advisor=tier(
                "ADVISOR"
            ),
        )

    @classmethod
    def from_file(
        cls,
        path: str | Path = ".env",
    ) -> "Settings":
        """Load settings from a .env file."""

        path = Path(path)

        return cls.from_values(
            load_dotenv(path),
            base_dir=(
                path.resolve().parent
            ),
        )
