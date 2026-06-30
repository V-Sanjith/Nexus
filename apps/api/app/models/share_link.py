from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class ShareLink(BaseModel):
    """Allows anonymous users to access a read-only compiled Decision Report."""
    __tablename__ = "share_links"

    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True, nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    decision: Mapped["Decision"] = relationship("Decision", back_populates="share_links")
