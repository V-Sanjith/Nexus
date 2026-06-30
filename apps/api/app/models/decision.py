from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class Decision(BaseModel):
    """Represents a single user decision session. Implements optimistic locking and soft delete."""
    __tablename__ = "decisions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False) # e.g. "laptop", "smartphone", "monitor"
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # e.g. "gaming", "ultrabook", "photography"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False) # PENDING, QUESTIONING, ANALYZING, COMPLETE, FAILED
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)
    detected_use_case: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # AI-inferred persona/use-case
    intent_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 0-100 classification confidence
    persona_weights: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # AI-generated custom weights
    
    # Version column for optimistic concurrency lock
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="decisions")
    questions: Mapped[List["Question"]] = relationship("Question", back_populates="decision", cascade="all, delete-orphan")
    answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="decision", cascade="all, delete-orphan")
    recommendation: Mapped["Recommendation"] = relationship("Recommendation", back_populates="decision", uselist=False, cascade="all, delete-orphan")
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="decision", cascade="all, delete-orphan")
    share_links: Mapped[List["ShareLink"]] = relationship("ShareLink", back_populates="decision", cascade="all, delete-orphan")
