from sqlalchemy import String, Numeric, Boolean, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import BaseModel

class Product(BaseModel):
    """The master catalog product details. Features specs matching and pricing mappings."""
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    price_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    specs: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # GIN Index for rapid specifications criteria search queries
    __table_args__ = (
        Index("idx_products_specs", "specs", postgresql_using="gin"),
    )
