import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.peer import Peer


class ConfigType(str, Enum):
    WIREGUARD = "wireguard"
    MIKROTIK_SCRIPT = "mikrotik-script"
    MIKROTIK_API = "mikrotik-api"
    IPTABLES = "iptables"
    NFTABLES = "nftables"


class ConfigurationHistory(Base):
    __tablename__ = "configuration_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    peer_id: Mapped[str] = mapped_column(String(36), ForeignKey("peers.id"), nullable=False)
    configuration_text: Mapped[str] = mapped_column(Text, nullable=False)
    config_type: Mapped[ConfigType] = mapped_column(SQLEnum(ConfigType), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    peer: Mapped["Peer"] = relationship("Peer", back_populates="config_history")
