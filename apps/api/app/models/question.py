from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class Question(BaseModel):
    """Dynamically compiled question mapping a decision's parameters."""
    __tablename__ = "questions"

    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(String(500), nullable=False)
    input_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. single_choice, multi_choice, budget_range, slider
    options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # e.g. {"choices": ["iOS", "Android"]}
    weight_impact: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Mapping how options translate to scoring parameters

    # Relationships
    decision: Mapped["Decision"] = relationship("Decision", back_populates="questions")
    answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="question")
