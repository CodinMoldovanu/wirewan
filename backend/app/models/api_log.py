import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.deployment import DeploymentJob
    from app.models.peer import Peer


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    DELETE = "DELETE"


class MikrotikApiCallLog(Base):
    __tablename__ = "mikrotik_api_call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deployment_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("deployment_jobs.id"), nullable=False)
    peer_id: Mapped[str] = mapped_column(String(36), ForeignKey("peers.id"), nullable=False)
    method: Mapped[HttpMethod] = mapped_column(SQLEnum(HttpMethod), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    request_body: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    deployment_job: Mapped["DeploymentJob"] = relationship("DeploymentJob", back_populates="api_call_logs")
