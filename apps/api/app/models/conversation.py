from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class Conversation(BaseModel):
    """Integrates an AI Copilot chat session bound to a specific Decision context."""
    __tablename__ = "conversations"

    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    # Relationships
    decision: Mapped["Decision"] = relationship("Decision", back_populates="conversations")
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(BaseModel):
    """A single bubble in the Copilot chat conversation."""
    __tablename__ = "messages"

    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    sender: Mapped[str] = mapped_column(String(50), nullable=False) # "USER", "NEXUS"
    content: Mapped[str] = mapped_column(String(5000), nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # suggestion pills clicklogs

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
