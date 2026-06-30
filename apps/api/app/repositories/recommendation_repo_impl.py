from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.recommendation import Recommendation
from app.repositories.recommendation_repo import IRecommendationRepository

class SQLAlchemyRecommendationRepository(IRecommendationRepository):
    """SQLAlchemy async implementation of the Recommendation Repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> Optional[Recommendation]:
        stmt = select(Recommendation).where(Recommendation.id == id).options(
            selectinload(Recommendation.verdict_product),
            selectinload(Recommendation.versions)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Recommendation]:
        stmt = select(Recommendation).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: Recommendation) -> Recommendation:
        self.session.add(entity)
        await self.session.flush()
        # Refresh to populate foreign keys and relationships
        stmt = select(Recommendation).where(Recommendation.id == entity.id).options(
            selectinload(Recommendation.verdict_product)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def update(self, entity: Recommendation) -> Recommendation:
        await self.session.flush()
        return entity

    async def delete(self, id: UUID) -> bool:
        entity = await self.get_by_id(id)
        if entity:
            await self.session.delete(entity)
            await self.session.flush()
            return True
        return False

    async def get_by_decision_id(self, decision_id: UUID) -> Optional[Recommendation]:
        stmt = select(Recommendation).where(Recommendation.decision_id == decision_id).options(
            selectinload(Recommendation.verdict_product),
            selectinload(Recommendation.versions)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
