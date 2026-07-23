from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import String, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class PriceObservation(BaseModel):
    """Historical and current price observation record from verified data sources."""
    __tablename__ = "price_observations"

    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="seed", nullable=False) # e.g. "seed", "flipkart", "amazon_in", "manual"
    source_url: Mapped[Optional[str]] = mapped_column(String(550), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    availability: Mapped[str] = mapped_column(String(50), default="in_stock", nullable=False) # "in_stock" | "out_of_stock" | "preorder" | "unknown"

    # Relationship
    product: Mapped["Product"] = relationship("Product")
