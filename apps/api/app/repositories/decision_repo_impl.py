from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.decision import Decision
from app.models.recommendation import Recommendation
from app.repositories.decision_repo import IDecisionRepository

class SQLAlchemyDecisionRepository(IDecisionRepository):
    """SQLAlchemy async implementation of the Decision Repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> Optional[Decision]:
        stmt = select(Decision).where(
            Decision.id == id,
            Decision.is_deleted == False
        ).options(
            selectinload(Decision.questions),
            selectinload(Decision.answers),
            selectinload(Decision.recommendation).selectinload(Recommendation.verdict_product)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Decision]:
        stmt = select(Decision).where(Decision.is_deleted == False).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: Decision) -> Decision:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def update(self, entity: Decision) -> Decision:
        await self.session.flush()
        return entity

    async def delete(self, id: UUID) -> bool:
        entity = await self.get_by_id(id)
        if entity:
            entity.is_deleted = True
            await self.session.flush()
            return True
        return False

    async def get_by_user_id(self, user_id: UUID, skip: int = 0, limit: int = 50) -> List[Decision]:
        stmt = select(Decision).where(
            Decision.user_id == user_id,
            Decision.is_deleted == False
        ).order_by(Decision.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_answers(self, decision_id: UUID) -> Optional[Decision]:
        # Same eager loading logic as get_by_id to fetch all related responses
        return await self.get_by_id(decision_id)
