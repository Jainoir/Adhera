"""Environment-driven configuration for the Notification and Escalation Service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "notification-service"
    debug: bool = False
    database_url: str = ""
    redis_url: str = ""
    rabbitmq_url: str = ""


settings = Settings()
