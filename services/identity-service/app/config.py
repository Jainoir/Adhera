"""Environment-driven configuration for the Identity and Consent Service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "identity-service"
    debug: bool = False
    database_url: str = ""
    redis_url: str = ""
    rabbitmq_url: str = ""


settings = Settings()
