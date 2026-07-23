import structlog
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = structlog.get_logger()

class SourceDefinition(BaseModel):
    source_name: str
    source_type: str # "official_manufacturer" | "verified_retailer" | "curated_catalog" | "web_discovery" | "estimated_seed"
    domain: Optional[str] = None
    supported_categories: List[str]
    trust_level: float # 0.0 to 1.0
    allowed_data_fields: List[str] # e.g. ["identity", "specs", "price", "image"]
    ingestion_method: str # "manual_audit" | "api" | "verified_crawler"
    is_active: bool = True

class SourceRegistry:
    """Centralized configurable registry of approved catalog data sources and trust levels."""

    REGISTRY: Dict[str, SourceDefinition] = {
        "seed_catalog_v2": SourceDefinition(
            source_name="seed_catalog_v2",
            source_type="curated_catalog",
            domain="nexus.internal",
            supported_categories=["laptop", "smartphone", "monitor"],
            trust_level=0.85,
            allowed_data_fields=["identity", "specs"],
            ingestion_method="manual_audit",
            is_active=True
        ),
        "official_store": SourceDefinition(
            source_name="official_store",
            source_type="official_manufacturer",
            domain="official.store",
            supported_categories=["laptop", "smartphone", "monitor"],
            trust_level=0.95,
            allowed_data_fields=["identity", "specs", "price", "image"],
            ingestion_method="api",
            is_active=True
        ),
        "amazon_in": SourceDefinition(
            source_name="amazon_in",
            source_type="verified_retailer",
            domain="amazon.in",
            supported_categories=["laptop", "smartphone", "monitor"],
            trust_level=0.90,
            allowed_data_fields=["price", "image"],
            ingestion_method="api",
            is_active=True
        ),
        "flipkart": SourceDefinition(
            source_name="flipkart",
            source_type="verified_retailer",
            domain="flipkart.com",
            supported_categories=["laptop", "smartphone", "monitor"],
            trust_level=0.90,
            allowed_data_fields=["price", "image"],
            ingestion_method="api",
            is_active=True
        ),
        "gemini_web_search": SourceDefinition(
            source_name="gemini_web_search",
            source_type="web_discovery",
            domain="google.com",
            supported_categories=["laptop", "smartphone", "monitor"],
            trust_level=0.60,
            allowed_data_fields=["identity", "specs", "price"],
            ingestion_method="verified_crawler",
            is_active=False # Off during closed alpha
        )
    }

    @classmethod
    def get_source(cls, name: str) -> Optional[SourceDefinition]:
        return cls.REGISTRY.get(name)

    @classmethod
    def is_approved_for_field(cls, source_name: str, field_group: str) -> bool:
        src = cls.get_source(source_name)
        if not src or not src.is_active:
            return False
        return field_group in src.allowed_data_fields
