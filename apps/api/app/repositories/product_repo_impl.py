from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from app.repositories.product_repo import IProductRepository

class SQLAlchemyProductRepository(IProductRepository):
    """SQLAlchemy async implementation of the Product Repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> Optional[Product]:
        return await self.session.get(Product, id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Product]:
        stmt = select(Product).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: Product) -> Product:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def update(self, entity: Product) -> Product:
        # SQLAlchemy tracks updates automatically inside session context
        await self.session.flush()
        return entity

    async def delete(self, id: UUID) -> bool:
        entity = await self.get_by_id(id)
        if entity:
            await self.session.delete(entity)
            await self.session.flush()
            return True
        return False

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        stmt = select(Product).where(Product.sku == sku)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_category(self, category: str, skip: int = 0, limit: Optional[int] = None, subtype: Optional[str] = None) -> List[Product]:
        from app.config import settings
        stmt = select(Product).where(
            Product.category == category, 
            Product.is_active == True,
            Product.ingestion_status == "recommendation_eligible"
        )
        if getattr(settings, "CATALOG_MODE", "production").lower() == "production":
            stmt = stmt.where(Product.source_type.in_(["real_seed", "web_enrichment_verified", "manual_verified", "manual"]))
        if subtype and subtype != "general":
            db_subtype = subtype
            if category == "laptop":
                if subtype == "programming":
                    db_subtype = "developer"
                subtype_key = "laptop_type"
            elif category == "smartphone":
                subtype_key = "phone_type"
            elif category == "monitor":
                if subtype == "designer" or subtype == "productivity":
                    db_subtype = "design"
                subtype_key = "monitor_type"
            else:
                subtype_key = None

            if subtype_key:
                if category == "smartphone":
                    stmt = stmt.where(Product.specs[subtype_key].as_string().in_([db_subtype, "flagship"]))
                elif category == "laptop":
                    stmt = stmt.where(Product.specs[subtype_key].as_string().in_([db_subtype, "premium"]))
                else:
                    stmt = stmt.where(Product.specs[subtype_key].as_string() == db_subtype)
        stmt = stmt.offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
            
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def query_specs(self, category: str, query_filters: dict) -> List[Product]:
        # Basic raw matching query: filters out active products matching criteria
        stmt = select(Product).where(
            Product.category == category,
            Product.is_active == True
        )
        # Apply JSONB contains criteria if filters are provided
        if query_filters:
            stmt = stmt.where(Product.specs.contains(query_filters))
            
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
