from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import Numeric, ForeignKey, String, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class Recommendation(BaseModel):
    """The final calculated decision engine output including verdict and analysis."""
    __tablename__ = "recommendations"

    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), unique=True, nullable=False)
    verdict_product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    structured_analysis: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False) # Pros/Cons/Tradeoffs/Alternatives
    explanation_md: Mapped[str] = mapped_column(String(10000), nullable=False)

    # Relationships
    decision: Mapped["Decision"] = relationship("Decision", back_populates="recommendation")
    verdict_product: Mapped["Product"] = relationship("Product")
    versions: Mapped[List["RecommendationVersion"]] = relationship("RecommendationVersion", back_populates="recommendation", cascade="all, delete-orphan")

class RecommendationVersion(BaseModel):
    """Logs recommendation updates when parameters or prices change."""
    __tablename__ = "recommendation_versions"

    recommendation_id: Mapped[UUID] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"), index=True, nullable=False)
    version_index: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_reason: Mapped[str] = mapped_column(String(255), nullable=False) # "priority_change", "price_drop", "spec_update"
    verdict_product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    delta_analysis: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False) # Change comparisons

    # Relationships
    recommendation: Mapped["Recommendation"] = relationship("Recommendation", back_populates="versions")
    verdict_product: Mapped["Product"] = relationship("Product")
