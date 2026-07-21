"""Environment-driven configuration for the Notification and Escalation Service."""

from shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "notification-service"


settings = Settings()
