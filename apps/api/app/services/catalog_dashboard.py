import structlog
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from app.models.product import Product

logger = structlog.get_logger()

class CatalogHealthDashboardService:
    """Internal admin service for calculating real-time catalog quality and coverage metrics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_health_metrics(self) -> Dict[str, Any]:
        """Gathers internal catalog quality metrics."""
        # 1. Total real product families
        stmt_fam = select(func.count(distinct(Product.product_family))).where(Product.source_type != "synthetic")
        res_fam = await self.session.execute(stmt_fam)
        real_families = res_fam.scalar() or 0

        # 2. Total real models
        stmt_mod = select(func.count(distinct(Product.model))).where(Product.source_type != "synthetic")
        res_mod = await self.session.execute(stmt_mod)
        real_models = res_mod.scalar() or 0

        # 3. Total real variants
        stmt_var = select(func.count(Product.id)).where(Product.source_type != "synthetic")
        res_var = await self.session.execute(stmt_var)
        real_variants = res_var.scalar() or 0

        # 4. Verified variants
        stmt_ver = select(func.count(Product.id)).where(
            Product.source_type != "synthetic",
            Product.verification_status != "unverified"
        )
        res_ver = await self.session.execute(stmt_ver)
        verified_variants = res_ver.scalar() or 0

        # 5. Synthetic test products
        stmt_syn = select(func.count(Product.id)).where(Product.source_type == "synthetic")
        res_syn = await self.session.execute(stmt_syn)
        synthetic_count = res_syn.scalar() or 0

        # 6. Products missing images
        stmt_no_img = select(func.count(Product.id)).where(
            Product.source_type != "synthetic",
            (Product.image_url == None) | (Product.image_url == "")
        )
        res_no_img = await self.session.execute(stmt_no_img)
        missing_images = res_no_img.scalar() or 0

        # 7. Products with unverified images
        stmt_unv_img = select(func.count(Product.id)).where(
            Product.source_type != "synthetic",
            Product.image_match_level == "unverified"
        )
        res_unv_img = await self.session.execute(stmt_unv_img)
        unverified_images = res_unv_img.scalar() or 0

        # 8. Category breakdown for real products
        stmt_cat = select(Product.category, func.count(Product.id)).where(
            Product.source_type != "synthetic"
        ).group_by(Product.category)
        res_cat = await self.session.execute(stmt_cat)
        category_breakdown = {cat: count for cat, count in res_cat.all()}

        return {
            "real_product_families": real_families,
            "real_models": real_models,
            "real_variants": real_variants,
            "verified_variants": verified_variants,
            "synthetic_test_products": synthetic_count,
            "products_missing_images": missing_images,
            "products_unverified_images": unverified_images,
            "category_coverage": category_breakdown,
            "verification_rate_pct": round((verified_variants / max(1, real_variants)) * 100, 2)
        }
