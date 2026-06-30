from typing import Generic, TypeVar, Optional, List
from uuid import UUID

T = TypeVar("T")

class IBaseRepository(Generic[T]):
    """Generic asynchronous data-access repository interface."""
    
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Fetch a single entity by its UUID primary key."""
        raise NotImplementedError

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Fetch a paginated list of all entities."""
        raise NotImplementedError

    async def create(self, entity: T) -> T:
        """Persist a new entity record."""
        raise NotImplementedError

    async def update(self, entity: T) -> T:
        """Update an existing entity record."""
        raise NotImplementedError

    async def delete(self, id: UUID) -> bool:
        """Delete an entity by its UUID key."""
        raise NotImplementedError
