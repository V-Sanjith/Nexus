from datetime import datetime, timezone
from typing import Dict, Any, Optional

class ProvenanceService:
    """Helper for field-level provenance tracking and 3-tier spec verification."""

    @staticmethod
    def evaluate_price_freshness(observed_at: Optional[datetime]) -> str:
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
    def classify_spec_verification(source_type: str, has_official_spec: bool = True) -> str:
        """
        Returns 3-tier spec verification state:
        - 'manufacturer_verified': Published specifications from official manufacturer page/spec sheet.
        - 'independently_verified': Lab measurements from trusted review sources.
        - 'unverified': Uncertain or estimated specification data.
        """
        if source_type in ["official_store", "official_manufacturer", "real_seed", "verified_retailer"] and has_official_spec:
            return "manufacturer_verified"
        elif source_type == "lab_verified":
            return "independently_verified"
        else:
            return "unverified"
