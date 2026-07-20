"""Environment-driven configuration for the Medication Service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "medication-service"
    debug: bool = False
    database_url: str = ""
    redis_url: str = ""
    rabbitmq_url: str = ""


settings = Settings()
