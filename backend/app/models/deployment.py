import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.peer import Peer
    from app.models.api_log import MikrotikApiCallLog
    from app.models.user import User


class JobType(str, Enum):
    DEPLOY_CONFIG = "deploy-config"
    ROLLBACK = "rollback"
    VERIFY = "verify"
    TEST_CONNECTION = "test-connection"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeploymentJob(Base):
    __tablename__ = "deployment_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    peer_id: Mapped[str] = mapped_column(String(36), ForeignKey("peers.id"), nullable=False)
    job_type: Mapped[JobType] = mapped_column(SQLEnum(JobType), nullable=False)
    status: Mapped[JobStatus] = mapped_column(SQLEnum(JobStatus), nullable=False, default=JobStatus.PENDING)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operations_log: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=list)
    backup_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    # Relationships
    peer: Mapped["Peer"] = relationship("Peer", back_populates="deployment_jobs")
    api_call_logs: Mapped[List["MikrotikApiCallLog"]] = relationship(
        "MikrotikApiCallLog", back_populates="deployment_job", cascade="all, delete-orphan"
    )
    created_by: Mapped[Optional["User"]] = relationship("User")
