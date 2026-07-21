"""Environment-driven configuration for the API Gateway."""

from shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "api-gateway"
    identity_service_url: str = "http://localhost:8001"
    medication_service_url: str = "http://localhost:8002"
    notification_service_url: str = "http://localhost:8003"


settings = Settings()
