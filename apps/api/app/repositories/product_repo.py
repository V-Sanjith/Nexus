from typing import List, Optional
from app.models.product import Product
from app.repositories.base import IBaseRepository

class IProductRepository(IBaseRepository[Product]):
    """Data-access interface for Product catalog operations."""

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        """Fetch a single product SKU card."""
        raise NotImplementedError

    async def get_by_category(self, category: str, skip: int = 0, limit: int = 100) -> List[Product]:
        """Fetch all active products in a specific category."""
        raise NotImplementedError

    async def query_specs(self, category: str, query_filters: dict) -> List[Product]:
        """Query catalog using JSONB spec matching parameters."""
        raise NotImplementedError
