import structlog
from typing import Any, Dict, Set
from app.config import settings

logger = structlog.get_logger()

class ProductionEligibilityPolicy:
    """Centralized, configurable policy engine for production catalog recommendation eligibility."""

    APPROVED_SOURCE_TYPES: Set[str] = {
        "real_seed",
        "web_enrichment_verified",
        "manual_verified",
        "manual"
    }

    MIN_SPEC_COVERAGE: Dict[str, float] = {
        "laptop": 0.75,
        "smartphone": 0.75,
        "monitor": 0.70
    }

    REQUIRED_IDENTITY_FIELDS = ["brand", "product_family", "model", "variant_key"]

    @classmethod
    def is_eligible(cls, product: Any, catalog_mode: str = None) -> bool:
        """
        Evaluates whether a product instance satisfies all requirements for recommendation eligibility.
        """
        mode = (catalog_mode or getattr(settings, "CATALOG_MODE", "production")).lower()

        # 1. Active check
        is_active = getattr(product, "is_active", True)
        if not is_active:
            return False

        # 2. Ingestion Status
        ingestion_status = getattr(product, "ingestion_status", "recommendation_eligible")
        if ingestion_status != "recommendation_eligible":
            return False

        # 3. Source Type Allowlist check in Production Mode
        source_type = str(getattr(product, "source_type", "real_seed")).lower()
        if mode == "production":
            if source_type not in cls.APPROVED_SOURCE_TYPES:
                return False

        # 4. Identity Fields check (for real catalog products)
        if source_type != "synthetic":
            for field in cls.REQUIRED_IDENTITY_FIELDS:
                val = getattr(product, field, None)
                if not val or not str(val).strip():
                    return False

        # 5. Spec Coverage check
        category = str(getattr(product, "category", "")).lower()
        min_cov = cls.MIN_SPEC_COVERAGE.get(category, 0.70)
        spec_cov = float(getattr(product, "spec_coverage", 0.0) or 0.0)
        # Seed products before dynamic calculation default to 0.75+
        if source_type != "synthetic" and spec_cov > 0.0 and spec_cov < min_cov:
            return False

        return True
