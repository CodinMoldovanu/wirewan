import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.peer import Peer


class PeerConnection(Base):
    __tablename__ = "peer_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    peer_a_id: Mapped[str] = mapped_column(String(36), ForeignKey("peers.id"), nullable=False)
    peer_b_id: Mapped[str] = mapped_column(String(36), ForeignKey("peers.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_handshake: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
