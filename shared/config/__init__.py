"""Shared configuration base for all Adhera services.

Every service defines its own ``Settings`` class subclassing
:class:`BaseServiceSettings`, overriding ``service_name`` and adding
service-specific fields. All values are environment-driven (12-factor);
secrets must only ever arrive via environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Environment-driven settings shared by every Adhera service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "adhera-service"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    database_url: str = ""
    redis_url: str = ""
    rabbitmq_url: str = ""
