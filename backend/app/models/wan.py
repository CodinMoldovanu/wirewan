import uuid
from datetime import datetime
from enum import Enum
from typing import List, TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.peer import Peer


class TopologyType(str, Enum):
    HUB_SPOKE = "hub-spoke"
    MESH = "mesh"
    HYBRID = "hybrid"


class WanNetwork(Base):
    __tablename__ = "wan_networks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    tunnel_ip_range: Mapped[str] = mapped_column(String(50), nullable=False, default="10.0.0.0/24")
    shared_services_range: Mapped[str] = mapped_column(String(50), nullable=False, default="10.0.5.0/24")
    topology_type: Mapped[TopologyType] = mapped_column(
        SQLEnum(TopologyType), nullable=False, default=TopologyType.MESH
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    peers: Mapped[List["Peer"]] = relationship("Peer", back_populates="wan", cascade="all, delete-orphan")
