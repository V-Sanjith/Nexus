import structlog
from typing import Dict, Any, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product

logger = structlog.get_logger()

# Definitions for Grid Matrix
LAPTOP_BUDGETS = [
    (0, 40000, "Under ₹40,000"),
    (40000, 60000, "₹40,000–₹60,000"),
    (60000, 80000, "₹60,000–₹80,000"),
    (80000, 100000, "₹80,000–₹1,00,000"),
    (100000, 150000, "₹1,00,000–₹1,50,000"),
    (150000, 1000000, "Above ₹1,50,000")
]

LAPTOP_USECASES = ["student", "programming", "business", "gaming", "creator", "portability", "general"]

PHONE_BUDGETS = [
    (0, 15000, "Under ₹15,000"),
    (15000, 25000, "₹15,000–₹25,000"),
    (25000, 40000, "₹25,000–₹40,000"),
    (40000, 60000, "₹40,000–₹60,000"),
    (60000, 80000, "₹60,000–₹80,000"),
    (80000, 1000000, "Above ₹80,000")
]

PHONE_USECASES = ["general", "camera", "gaming", "battery", "performance", "compact", "value"]

MONITOR_BUDGETS = [
    (0, 15000, "Under ₹15,000"),
    (15000, 25000, "₹15,000–₹25,000"),
    (25000, 40000, "₹25,000–₹40,000"),
    (40000, 60000, "₹40,000–₹60,000"),
    (60000, 1000000, "Above ₹60,000")
]

MONITOR_USECASES = ["general", "programming", "gaming", "competitive", "designer", "highres"]

# Unrealistic/Invalid Commercially N/A combinations
INVALID_COMBINATIONS = {
    ("laptop", "Under ₹40,000", "creator"): "Heavy 4K video editing hardware requires discrete GPU and color-accurate panel not available under ₹40k.",
    ("laptop", "Under ₹40,000", "gaming"): "Modern AAA gaming requires dedicated GPU not viable under ₹40k MSRP.",
    ("smartphone", "Above ₹80,000", "value"): "Value-tier phone queries are commercially irrelevant at flagship ₹80k+ prices.",
    ("monitor", "Under ₹15,000", "highres"): "Native 4K resolution displays are not manufactured under ₹15,000 MSRP.",
    ("monitor", "Above ₹60,000", "budget"): "Budget monitor intent is mutually exclusive with >₹60,000 high-end pricing."
}

class CoverageGridService:
    """Service to construct, classify, and track the Minimum Viable Catalog Coverage Grid."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_grid(self) -> Dict[str, Any]:
        result = await self.session.execute(select(Product).where(Product.source_type == "real_seed", Product.is_active == True))
        products = result.scalars().all()

        cells = []
        
        def process_category(category: str, budgets: List[Tuple[int, int, str]], usecases: List[str]):
            for min_b, max_b, b_label in budgets:
                for uc in usecases:
                    na_reason = INVALID_COMBINATIONS.get((category, b_label, uc))
                    if na_reason:
                        cells.append({
                            "category": category,
                            "budget_label": b_label,
                            "use_case": uc,
                            "status": "N/A",
                            "distinct_models": 0,
                            "models": [],
                            "brands": [],
                            "na_reason": na_reason
                        })
                        continue

                    # Filter products for cell
                    matching_models = set()
                    matching_brands = set()
                    
                    for p in products:
                        if p.category != category:
                            continue
                        if not (min_b <= p.price_inr <= max_b):
                            continue
                            
                        # Check use case suitability from specs/tags
                        p_specs = p.specs or {}
                        p_tags = p_specs.get("tags", [])
                        p_type = p_specs.get("laptop_type") or p_specs.get("phone_type") or p_specs.get("monitor_type") or ""
                        
                        is_match = (
                            uc in p_tags or 
                            uc == p_type.lower() or 
                            uc == "general" or 
                            (uc == "programming" and p_type in ["student", "business", "developer"]) or
                            (uc == "compact" and float(p_specs.get("screen_size", 6.5)) <= 6.2) or
                            (uc == "battery" and (float(p_specs.get("battery_mah", 4000)) >= 5000 or float(p_specs.get("battery_capacity_wh", 40)) >= 50))
                        )
                        
                        if is_match:
                            matching_models.add(p.model)
                            if p.brand: matching_brands.add(p.brand)

                    m_count = len(matching_models)
                    if m_count == 0:
                        status = "EMPTY"
                    elif m_count <= 2:
                        status = "CRITICAL"
                    elif m_count <= 4:
                        status = "WEAK"
                    else:
                        status = "HEALTHY"

                    cells.append({
                        "category": category,
                        "budget_label": b_label,
                        "use_case": uc,
                        "status": status,
                        "distinct_models": m_count,
                        "models": list(matching_models),
                        "brands": list(matching_brands),
                        "na_reason": None
                    })

        process_category("laptop", LAPTOP_BUDGETS, LAPTOP_USECASES)
        process_category("smartphone", PHONE_BUDGETS, PHONE_USECASES)
        process_category("monitor", MONITOR_BUDGETS, MONITOR_USECASES)

        # Calculate macro statistics
        valid_cells = [c for c in cells if c["status"] != "N/A"]
        total_valid = len(valid_cells)
        empty_cnt = sum(1 for c in valid_cells if c["status"] == "EMPTY")
        critical_cnt = sum(1 for c in valid_cells if c["status"] == "CRITICAL")
        weak_cnt = sum(1 for c in valid_cells if c["status"] == "WEAK")
        healthy_cnt = sum(1 for c in valid_cells if c["status"] == "HEALTHY")

        return {
            "total_cells": len(cells),
            "valid_cells": total_valid,
            "na_cells": len(cells) - total_valid,
            "counts": {
                "EMPTY": empty_cnt,
                "CRITICAL": critical_cnt,
                "WEAK": weak_cnt,
                "HEALTHY": healthy_cnt
            },
            "percentages": {
                "EMPTY": round((empty_cnt / max(1, total_valid)) * 100, 1),
                "CRITICAL": round((critical_cnt / max(1, total_valid)) * 100, 1),
                "WEAK": round((weak_cnt / max(1, total_valid)) * 100, 1),
                "HEALTHY": round((healthy_cnt / max(1, total_valid)) * 100, 1)
            },
            "cells": cells
        }
