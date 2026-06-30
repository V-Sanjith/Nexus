from typing import Optional
from app.models.user import User
from app.repositories.base import IBaseRepository

class IUserRepository(IBaseRepository[User]):
    """Data-access interface for User account operations."""

    async def get_by_email(self, email: str) -> Optional[User]:
        """Fetch a single user profile matching the given email address."""
        raise NotImplementedError

    async def get_with_profile(self, user_id: str) -> Optional[User]:
        """Fetch a user record joined with profile and preferences."""
        raise NotImplementedError
