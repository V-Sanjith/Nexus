from typing import List, Optional
from uuid import UUID
from app.models.decision import Decision
from app.repositories.base import IBaseRepository

class IDecisionRepository(IBaseRepository[Decision]):
    """Data-access interface for Decision session operations."""

    async def get_by_user_id(self, user_id: UUID, skip: int = 0, limit: int = 50) -> List[Decision]:
        """Fetch decisions list created by a specific user sorted by date."""
        raise NotImplementedError

    async def get_with_answers(self, decision_id: UUID) -> Optional[Decision]:
        """Fetch decision record pre-joined with questions and submitted answers."""
        raise NotImplementedError
