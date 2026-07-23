import structlog
from typing import List, Dict, Any, Tuple
from app.models.product import Product

logger = structlog.get_logger()

class DeduplicationService:
    """Variant-aware structured deduplication service for catalog products."""

    @staticmethod
    def generate_variant_key(product: Product) -> str:
        """Generates a normalized identity variant key based on structured specs."""
        specs = product.specs or {}
        category = str(product.category).lower()
        brand = str(product.brand or specs.get("brand") or "").lower().strip()
        model = str(product.model or product.name or "").lower().strip()

        if category == "smartphone":
            ram = specs.get("ram_gb", "")
            stor = specs.get("storage_gb", "")
            return f"{brand}:{model}:{ram}gb-{stor}gb"
        elif category == "laptop":
            ram = specs.get("ram_gb", "")
            stor = specs.get("storage_gb", "")
            cpu = str(specs.get("cpu_model") or specs.get("cpu") or "").lower().strip()
            return f"{brand}:{model}:{cpu}:{ram}gb-{stor}gb"
        elif category == "monitor":
            size = specs.get("screen_size_inches") or specs.get("screen_size", "")
            res = specs.get("resolution_p", "")
            refresh = specs.get("refresh_rate_hz", "")
            panel = str(specs.get("panel_type") or "").lower().strip()
            return f"{brand}:{model}:{size}in-{res}p-{refresh}hz-{panel}"
        else:
            return f"{brand}:{model}:{product.sku}"

    @classmethod
    def audit_duplicates(cls, products: List[Product]) -> Tuple[List[Product], List[Product], Dict[str, Any]]:
        """
        Groups products by category + variant_key.
        Returns (canonical_products, duplicate_products, summary_stats).
        """
        clusters: Dict[str, List[Product]] = {}
        for p in products:
            vk = cls.generate_variant_key(p)
            cluster_key = f"{p.category}:{vk}"
            clusters.setdefault(cluster_key, []).append(p)

        canonical_list: List[Product] = []
        duplicate_list: List[Product] = []

        for c_key, group in clusters.items():
            if len(group) == 1:
                canonical_list.append(group[0])
            else:
                # Sort by spec_coverage desc, confidence_level desc, source_type rank
                def sort_rank(prod: Product):
                    src_rank = 3 if prod.source_type == "real_seed" else 2 if "verified" in prod.source_type else 1
                    return (src_rank, float(prod.spec_coverage or 0), float(prod.confidence_level or 0))

                sorted_group = sorted(group, key=sort_rank, reverse=True)
                canonical = sorted_group[0]
                duplicates = sorted_group[1:]

                canonical_list.append(canonical)
                duplicate_list.extend(duplicates)

        stats = {
            "total_input": len(products),
            "canonical_count": len(canonical_list),
            "duplicate_count": len(duplicate_list),
            "duplicate_rate_pct": round((len(duplicate_list) / max(1, len(products))) * 100, 2)
        }

        logger.info("Deduplication audit complete", **stats)
        return canonical_list, duplicate_list, stats
