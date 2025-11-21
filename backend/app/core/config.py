from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    APP_NAME: str = "WireWAN Overlay Manager"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./wirewan.db"

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Encryption key for sensitive data (credentials, private keys)
    # REQUIRED: Must be set in production - application will fail to start without it
    ENCRYPTION_KEY: Optional[str] = None

    # Salt for key derivation - should be unique per installation
    # REQUIRED: Must be set in production - application will fail to start without it
    ENCRYPTION_SALT: Optional[str] = None

    # Default network settings
    DEFAULT_TUNNEL_IP_RANGE: str = "10.0.0.0/24"
    DEFAULT_SHARED_SERVICES_RANGE: str = "10.0.5.0/24"
    DEFAULT_WIREGUARD_PORT: int = 51820

    # MikroTik defaults
    MIKROTIK_DEFAULT_API_PORT: int = 8728
    MIKROTIK_DEFAULT_INTERFACE_NAME: str = "wg-wan-overlay"

    # Deployment settings
    MAX_CONCURRENT_DEPLOYMENTS: int = 10
    DEPLOYMENT_TIMEOUT_SECONDS: int = 300

    # DNS / Pi-hole integration
    DNS_SUFFIX: str = "lan"
    PIHOLE_API_URL: Optional[str] = None  # e.g., http://pihole.local/admin/api.php
    PIHOLE_API_TOKEN: Optional[str] = None
    PIHOLE_VERIFY_SSL: bool = True

    # Deploy approvals / execution
    REQUIRE_DEPLOY_APPROVAL: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
