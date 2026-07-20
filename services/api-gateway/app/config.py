"""Environment-driven configuration for the API Gateway."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "api-gateway"
    debug: bool = False
    database_url: str = ""
    redis_url: str = ""
    rabbitmq_url: str = ""


settings = Settings()
