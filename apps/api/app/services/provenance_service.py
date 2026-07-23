from datetime import datetime, timezone
from typing import Dict, Any, Optional

class ProvenanceService:
    """Helper for field-level provenance tracking and price freshness evaluation."""

    @staticmethod
    def evaluate_price_freshness(observed_at: Optional[datetime]) -> str:
        """
        Returns price freshness state: FRESH (<7d), AGING (7-30d), STALE (>30d), UNKNOWN.
        """
        if not observed_at:
            return "UNKNOWN"
        
        now = datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
            
        days = (now - observed_at).days
        if days < 7:
            return "FRESH"
        elif days <= 30:
            return "AGING"
        else:
            return "STALE"

    @staticmethod
    def build_field_provenance(identity_src="seed_catalog_v2", spec_src="seed_catalog_v2", price_src=None, image_src=None) -> Dict[str, Any]:
        return {
            "identity_source": identity_src,
            "spec_source": spec_src,
            "price_source": price_src or "unverified_estimate",
            "image_source": image_src or "unverified_placeholder"
        }
