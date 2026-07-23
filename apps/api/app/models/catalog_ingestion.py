from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, JSON, DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import BaseModel

class CatalogIngestion(BaseModel):
    """Audit trail for product ingestion pipeline lifecycle steps."""
    __tablename__ = "catalog_ingestions"

    trigger: Mapped[str] = mapped_column(String(50), default="manual", nullable=False) # "manual" | "background_enrichment" | "admin_api"
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="gemini_search", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="discovered", index=True, nullable=False) # DISCOVERED -> PARSED -> NORMALIZED -> DEDUPLICATED -> VALIDATED -> VERIFIED -> RECOMMENDATION_ELIGIBLE | REJECTED
    products_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products_deduplicated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products_eligible: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw_response: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
