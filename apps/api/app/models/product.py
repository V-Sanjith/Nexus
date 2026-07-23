from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, Boolean, Index, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import BaseModel

class Product(BaseModel):
    """The master catalog product details. Features specs matching and pricing mappings with rich provenance tracking."""
    __tablename__ = "products"

    # Core Identifiers
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    price_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    specs: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Structured Product Identity
    brand: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    product_family: Mapped[Optional[str]] = mapped_column(String(150), index=True, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(150), index=True, nullable=True)
    variant_key: Mapped[Optional[str]] = mapped_column(String(200), index=True, nullable=True)

    # Source & Provenance
    source_type: Mapped[str] = mapped_column(String(50), default="real_seed", index=True, nullable=False) # "real_seed" | "synthetic" | "web_enrichment" | "manual"
    source_reference: Mapped[Optional[str]] = mapped_column(String(550), nullable=True)
    discovery_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Separate Granular Verification Dimensions
    identity_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    spec_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    price_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(50), default="unverified", nullable=False) # "unverified" | "partially_verified" | "fully_verified"
    confidence_level: Mapped[float] = mapped_column(Numeric(3, 2), default=0.70, nullable=False)
    spec_coverage: Mapped[float] = mapped_column(Numeric(3, 2), default=0.0, nullable=False)

    # Image Integrity
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_match_level: Mapped[str] = mapped_column(String(50), default="unverified", nullable=False) # "verified_exact_variant" | "verified_exact_model" | "verified_product_family" | "unverified" | "unavailable"

    # Ingestion Lifecycle State
    ingestion_status: Mapped[str] = mapped_column(String(50), default="recommendation_eligible", index=True, nullable=False) # "recommendation_eligible" | "validated" | "pending_review" | "rejected" | "deduplicated"

    # Indexes
    __table_args__ = (
        Index("idx_products_specs", "specs", postgresql_using="gin"),
        Index("idx_products_cat_active_elig", "category", "is_active", "ingestion_status", "source_type"),
        Index("idx_products_price_lookup", "category", "price_inr"),
        Index("idx_products_variant_dedup", "brand", "product_family", "variant_key"),
    )
