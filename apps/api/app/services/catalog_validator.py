from typing import List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from app.services.currency_service import CurrencyService
import structlog

logger = structlog.get_logger()

class CatalogValidator:
    """Performs rigorous Stage 4 catalog integrity audits and price-band validation on startup."""

    @staticmethod
    def validate_sku(product: Product) -> Tuple[bool, str]:
        """Enforces strict catalog integrity rules to prevent impossible SKUs."""
        sku = product.sku.lower()
        name = product.name.lower()
        specs = product.specs
        
        from app.services.score_calculator import ScoreCalculator
        ram = ScoreCalculator._safe_float(specs.get("ram_gb"), 0)
        storage = ScoreCalculator._safe_float(specs.get("storage_gb"), 0)
        cpu = str(specs.get("cpu_model") or "").lower()
        gpu = str(specs.get("gpu_name") or "").lower()
        refresh = ScoreCalculator._safe_float(specs.get("refresh_rate_hz"), 0)
        
        # 1. Apple MacBook Integrity Rules
        if "apple" in sku or "macbook" in name:
            if "rtx" in gpu or "nvidia" in gpu:
                return False, f"Apple MacBook '{product.sku}' cannot have dedicated NVIDIA RTX GPU."
            if "geforce" in gpu:
                return False, f"Apple MacBook '{product.sku}' cannot have dedicated GeForce GPU."
            if refresh > 120:
                return False, f"Apple MacBook '{product.sku}' cannot have a high-end refresh rate of {refresh}Hz."
            if "macbook pro" in name and ram < 16:
                return False, f"Apple MacBook Pro '{product.sku}' cannot be configured with less than 16GB RAM."

        # 2. Budget Laptop Integrity Rules
        if "pavilion" in sku or "aspire" in sku or "vivobook" in sku or specs.get("laptop_type") == "student":
            if "4090" in gpu or "4080" in gpu:
                return False, f"Budget student laptop '{product.sku}' cannot have enthusiast dedicated GPU '{gpu}'."
            if ram >= 64:
                return False, f"Budget student laptop '{product.sku}' cannot have premium RAM configuration of {ram}GB."
            if storage > 1024:
                return False, f"Budget student laptop '{product.sku}' cannot have premium storage configuration of {storage}GB."

        # 3. Enthusiast Gaming Laptop (ROG SCAR) Integrity Rules
        if "scar" in sku or "raider" in sku:
            if ram < 16:
                return False, f"Enthusiast gaming laptop '{product.sku}' cannot have less than 16GB RAM."
            if storage < 512:
                return False, f"Enthusiast gaming laptop '{product.sku}' cannot have less than 512GB SSD."
            if "rtx" not in gpu and "dedicated" not in specs.get("gpu_type", ""):
                return False, f"Enthusiast gaming laptop '{product.sku}' must have a dedicated gaming GPU."

        # 4. Business Laptop Integrity Rules
        if specs.get("laptop_type") == "business":
            if "4090" in gpu or "4080" in gpu:
                return False, f"Business laptop '{product.sku}' cannot have enthusiast gaming GPU '{gpu}'."

        return True, ""

    @classmethod
    async def validate_catalog(cls, session: AsyncSession):
        """Validates catalog integrity and prints/logs a complete price-band audit report."""
        logger.info("Stage 4: Starting Catalog Validation Audit...")
        
        stmt = select(Product).where(Product.is_active == True)
        res = await session.execute(stmt)
        products = res.scalars().all()
        
        logger.info(f"Loaded {len(products)} products for integrity checks.")
        
        # 1. Perform SKU Integrity Validation
        invalid_count = 0
        for p in products:
            is_valid, reason = cls.validate_sku(p)
            if not is_valid:
                logger.critical("CATALOG INTEGRITY FAILURE: Product violates configuration rules!", sku=p.sku, name=p.name, reason=reason)
                invalid_count += 1
                raise ValueError(f"Catalog Integrity Failure: {reason}")

        logger.info("SKU Integrity Validation: PASSED. Zero invalid configurations found.")

        # 2. Perform Subtype Price-Band Coverage Audit
        # Partition products by Category and Subtype
        catalog_by_subtype = {}
        for p in products:
            cat = p.category
            sub = p.specs.get("laptop_type") or p.specs.get("phone_type") or p.specs.get("monitor_type") or "general"
            key = (cat, sub)
            catalog_by_subtype.setdefault(key, []).append(p)

        # Audit definitions for price bands (in INR)
        # We define price bands for Laptops, Phones, and Monitors in INR
        for (cat, sub), sub_products in catalog_by_subtype.items():
            prices_inr = [float(p.price_inr) for p in sub_products]
            prices_inr.sort()
            
            min_p = min(prices_inr)
            max_p = max(prices_inr)
            avg_p = sum(prices_inr) / len(prices_inr)
            n = len(prices_inr)
            median_p = prices_inr[n // 2] if n % 2 != 0 else (prices_inr[n // 2 - 1] + prices_inr[n // 2]) / 2.0
            
            logger.info(f"Subtype Audit Summary: {cat}/{sub} - Count: {n}, Range: ₹{min_p:,.0f} - ₹{max_p:,.0f}, Median: ₹{median_p:,.0f}")
            
            # Subtype-specific price band audits
            if cat == "laptop" and sub == "gaming":
                bands = {
                    "< ₹50k": lambda p: p < 50000,
                    "₹50k-70k": lambda p: 50000 <= p < 70000,
                    "₹70k-90k": lambda p: 70000 <= p < 90000,
                    "₹90k-110k": lambda p: 90000 <= p < 110000,
                    "₹110k-150k": lambda p: 110000 <= p < 150000,
                    "> ₹150k": lambda p: p >= 150000
                }
                for band_name, condition in bands.items():
                    matching_count = len([p for p in prices_inr if condition(p)])
                    if matching_count == 0:
                        logger.warning(f"PRICE BAND EMPTY WARNING: {cat}/{sub} has zero products in the '{band_name}' price band!")
                    else:
                        logger.info(f"  Price Band '{band_name}': {matching_count} products.")
                        
            elif cat == "laptop" and sub == "business":
                bands = {
                    "< ₹60k": lambda p: p < 60000,
                    "₹60k-100k": lambda p: 60000 <= p < 100000,
                    "₹100k-140k": lambda p: 100000 <= p < 140000,
                    "> ₹140k": lambda p: p >= 140000
                }
                for band_name, condition in bands.items():
                    matching_count = len([p for p in prices_inr if condition(p)])
                    if matching_count == 0:
                        logger.warning(f"PRICE BAND EMPTY WARNING: {cat}/{sub} has zero products in the '{band_name}' price band!")
            
            elif cat == "smartphone" and sub == "budget":
                bands = {
                    "< ₹25k": lambda p: p < 25000,
                    "₹25k-35k": lambda p: 25000 <= p < 35000,
                    "₹35k-50k": lambda p: 35000 <= p < 50000
                }
                for band_name, condition in bands.items():
                    matching_count = len([p for p in prices_inr if condition(p)])
                    if matching_count == 0:
                        logger.warning(f"PRICE BAND EMPTY WARNING: {cat}/{sub} has zero products in the '{band_name}' price band!")

        logger.info("Stage 4: Catalog Validation Audit complete.")
