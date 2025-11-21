import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.peer import Peer


class ServiceProtocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    BOTH = "both"


class PublishedService(Base):
    __tablename__ = "published_services"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    peer_id: Mapped[str] = mapped_column(String(36), ForeignKey("peers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    local_ip: Mapped[str] = mapped_column(String(50), nullable=False)
    local_port: Mapped[int] = mapped_column(Integer, nullable=False)
    shared_ip: Mapped[str] = mapped_column(String(50), nullable=False)
    shared_port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[ServiceProtocol] = mapped_column(
        SQLEnum(ServiceProtocol), nullable=False, default=ServiceProtocol.TCP
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    peer: Mapped["Peer"] = relationship("Peer", back_populates="published_services")
