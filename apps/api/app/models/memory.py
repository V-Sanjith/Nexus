from uuid import UUID
from sqlalchemy import String, Numeric, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class DecisionMemory(BaseModel):
    """Stores user preferences (e.g. brand blacklists or requirements) across sessions."""
    __tablename__ = "decision_memories"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    domain_key: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. preferred_brand, max_weight
    domain_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), default=1.00, nullable=False) # scale of 0.00 to 1.00

    # Ensure unique memory keys per user
    __table_args__ = (
        UniqueConstraint("user_id", "domain_key", name="uq_memories_user_domain_key"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="memories")
