from uuid import UUID
from sqlalchemy import ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class Answer(BaseModel):
    """Stores user responses to dynamic questions during requirements gathering."""
    __tablename__ = "answers"

    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True, nullable=False)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False)
    selected_value: Mapped[dict] = mapped_column(JSON, nullable=False) # raw answer data

    # Unique constraint: A single question can only be answered once per decision session
    __table_args__ = (
        UniqueConstraint("decision_id", "question_id", name="uq_answers_decision_question"),
    )

    # Relationships
    decision: Mapped["Decision"] = relationship("Decision", back_populates="answers")
    question: Mapped["Question"] = relationship("Question", back_populates="answers")
