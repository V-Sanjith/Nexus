from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import BigInteger, String, ForeignKey, DateTime, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class AuditLog(Base):
    """System-wide security and operations audit ledger."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False) # e.g. "USER_LOGIN", "DECISION_COMPLETED"
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Full event variables context
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
