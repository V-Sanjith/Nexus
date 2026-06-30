from typing import Optional
from sqlalchemy import String, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import BaseModel

class FeatureFlag(BaseModel):
    """Database-backed feature flags allowing dynamic targeting rules in production."""
    __tablename__ = "feature_flags"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False) # e.g. "ENABLE_COPILOT"
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Targeting criteria (e.g. {"percent_rollout": 20})
