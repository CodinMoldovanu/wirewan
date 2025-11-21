import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.peer import Peer


class LocalSubnet(Base):
    __tablename__ = "local_subnets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    peer_id: Mapped[str] = mapped_column(String(36), ForeignKey("peers.id"), nullable=False)
    cidr: Mapped[str] = mapped_column(String(50), nullable=False)
    is_routed: Mapped[bool] = mapped_column(Boolean, default=True)
    nat_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    nat_translated_cidr: Mapped[str] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationships
    peer: Mapped["Peer"] = relationship("Peer", back_populates="local_subnets")
