"""Environment-driven configuration for the Medication Service."""

from shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "medication-service"


settings = Settings()
