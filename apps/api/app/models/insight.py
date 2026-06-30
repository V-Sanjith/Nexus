from typing import Optional
from uuid import UUID
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class Insight(BaseModel):
    """User behavioral insights and streak records compiled by backend workers."""
    __tablename__ = "insights"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "spending_pattern", "loyalty_streak"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Custom graphs payload

    # Relationships
    user: Mapped["User"] = relationship("User")
