import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, Integer, Boolean, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.wan import WanNetwork
    from app.models.subnet import LocalSubnet
    from app.models.service import PublishedService
    from app.models.config_history import ConfigurationHistory
    from app.models.deployment import DeploymentJob


class PeerType(str, Enum):
    MIKROTIK = "mikrotik"
    GENERIC_ROUTER = "generic-router"
    SERVER = "server"
    CLIENT = "client"
    HUB = "hub"


class MikrotikAuthMethod(str, Enum):
    PASSWORD = "password"
    TOKEN = "token"


class MikrotikApiStatus(str, Enum):
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    AUTH_FAILED = "auth-failed"
    UNREACHABLE = "unreachable"


class Peer(Base):
    __tablename__ = "peers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wan_id: Mapped[str] = mapped_column(String(36), ForeignKey("wan_networks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[PeerType] = mapped_column(SQLEnum(PeerType), nullable=False)

    # Wireguard settings
    public_key: Mapped[str] = mapped_column(String(44), nullable=True)  # Base64 encoded
    private_key_encrypted: Mapped[str] = mapped_column(Text, nullable=True)  # Encrypted
    tunnel_ip: Mapped[str] = mapped_column(String(50), nullable=True)
    endpoint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # "ip:port"
    listen_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    persistent_keepalive: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=25)

    # Status
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Metadata
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=list)
    peer_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # MikroTik-specific fields
    mikrotik_management_ip: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mikrotik_api_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=8728)
    mikrotik_auth_method: Mapped[Optional[MikrotikAuthMethod]] = mapped_column(
        SQLEnum(MikrotikAuthMethod), nullable=True
    )
    mikrotik_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mikrotik_password_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mikrotik_api_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mikrotik_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    mikrotik_verify_cert: Mapped[bool] = mapped_column(Boolean, default=False)
    mikrotik_auto_deploy: Mapped[bool] = mapped_column(Boolean, default=False)
    mikrotik_interface_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default="wg-wan-overlay"
    )
    mikrotik_last_api_check: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    mikrotik_api_status: Mapped[Optional[MikrotikApiStatus]] = mapped_column(
        SQLEnum(MikrotikApiStatus), nullable=True, default=MikrotikApiStatus.UNKNOWN
    )
    mikrotik_router_identity: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mikrotik_routeros_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    wan: Mapped["WanNetwork"] = relationship("WanNetwork", back_populates="peers")
    local_subnets: Mapped[List["LocalSubnet"]] = relationship(
        "LocalSubnet", back_populates="peer", cascade="all, delete-orphan"
    )
    published_services: Mapped[List["PublishedService"]] = relationship(
        "PublishedService", back_populates="peer", cascade="all, delete-orphan"
    )
    config_history: Mapped[List["ConfigurationHistory"]] = relationship(
        "ConfigurationHistory", back_populates="peer", cascade="all, delete-orphan"
    )
    deployment_jobs: Mapped[List["DeploymentJob"]] = relationship(
        "DeploymentJob", back_populates="peer", cascade="all, delete-orphan"
    )
