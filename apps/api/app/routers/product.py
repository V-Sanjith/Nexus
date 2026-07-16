from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional

from app.dependencies import get_db
from app.models.product import Product
from app.repositories.product_repo_impl import SQLAlchemyProductRepository

router = APIRouter(prefix="/api/products", tags=["Products"])

@router.get("/{sku}")
async def get_product(sku: str, db: AsyncSession = Depends(get_db)):
    """Fetch details of a single product by its SKU, including similar alternatives."""
    repo = SQLAlchemyProductRepository(db)
    product = await repo.get_by_sku(sku)
    if not product:
        # Try to find by partial match on name or SKU
        stmt = select(Product).where(Product.name.ilike(f"%{sku}%")).limit(1)
        result = await db.execute(stmt)
        product = result.scalars().first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with SKU or name '{sku}' not found."
            )
            
    # Load similar alternatives from different families (same category, price +/- 35%, excluding current product)
    price = float(product.price_inr)
    stmt = select(Product).where(
        Product.category == product.category,
        Product.sku != product.sku,
        Product.price_inr.between(price * 0.65, price * 1.35),
        Product.is_active == True
    ).limit(20)
    result = await db.execute(stmt)
    candidates = result.scalars().all()
    
    # Deduplicate by family
    current_family = product.name.split(" (")[0].strip()
    alt_list = []
    seen_families = {current_family}
    for cand in candidates:
        cand_family = cand.name.split(" (")[0].strip()
        if cand_family not in seen_families:
            seen_families.add(cand_family)
            alt_list.append({
                "sku": cand.sku,
                "name": cand.name,
                "price_inr": float(cand.price_inr),
                "specs": cand.specs
            })
            if len(alt_list) >= 4:  # Pull up to 4 alternatives for rich comparison
                break
        
    # Find all configurations of the same family
    stmt = select(Product).where(
        Product.name.like(f"{current_family}%"),
        Product.is_active == True
    )
    result = await db.execute(stmt)
    variants = result.scalars().all()
    
    config_list = []
    for v in variants:
        name_parts = v.name.split(" (")
        config_name = name_parts[1].replace(")", "") if len(name_parts) > 1 else "Standard"
        config_list.append({
            "sku": v.sku,
            "name": config_name,
            "price_inr": float(v.price_inr)
        })

    # Calculate domain suitability scores dynamically
    from app.services.score_calculator import ScoreCalculator
    scores = ScoreCalculator.calculate_all(product.category, product.specs, float(product.price_inr))
    domain_scores = {k.replace("_score", ""): round(v * 10, 1) for k, v in scores.items()}
        
    return {
        "sku": product.sku,
        "name": product.name,
        "category": product.category,
        "price_inr": float(product.price_inr),
        "specs": product.specs,
        "alternatives": alt_list,
        "configurations": config_list,
        "domain_scores": domain_scores
    }
