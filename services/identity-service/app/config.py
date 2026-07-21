"""Environment-driven configuration for the Identity and Consent Service."""

from shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "identity-service"


settings = Settings()
