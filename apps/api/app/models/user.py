from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Boolean, DateTime, func, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class User(BaseModel):
    """User accounts registration table. Supports soft deletes."""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    dna: Mapped["UserDecisionDNA"] = relationship("UserDecisionDNA", back_populates="user", uselist=False, cascade="all, delete-orphan")
    decisions: Mapped[List["Decision"]] = relationship("Decision", back_populates="user", cascade="all, delete-orphan")
    memories: Mapped[List["DecisionMemory"]] = relationship("DecisionMemory", back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user", cascade="all, delete-orphan")

class UserProfile(BaseModel):
    """Extends user accounts with details and UI theme preferences."""
    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")

class UserDecisionDNA(BaseModel):
    """Stores the long-term calculated behavioral personas and priority bias vectors."""
    __tablename__ = "user_decision_dna"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    traits: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False) # e.g. {"price_sensitivity": 0.4, "risk_tolerance": 0.8}
    last_calculated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="dna")
