from typing import Optional
from uuid import UUID
from app.models.recommendation import Recommendation
from app.repositories.base import IBaseRepository

class IRecommendationRepository(IBaseRepository[Recommendation]):
    """Data-access interface for Recommendation output operations."""

    async def get_by_decision_id(self, decision_id: UUID) -> Optional[Recommendation]:
        """Fetch recommendation output bound to a decision context."""
        raise NotImplementedError
