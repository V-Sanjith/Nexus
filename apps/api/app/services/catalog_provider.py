from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from app.repositories.product_repo_impl import SQLAlchemyProductRepository
import structlog

logger = structlog.get_logger()

class CatalogProvider(ABC):
    """Abstract interface for all product search and spec retrieval providers."""

    @abstractmethod
    async def get_products(self, category: str, query: Optional[str] = None) -> List[Product]:
        """Retrieves active products in the category matching optional query criteria."""
        pass


class LocalCatalogProvider(CatalogProvider):
    """Accesses the locally seeded database catalog using SQLAlchemy repositories."""

    def __init__(self, session: AsyncSession):
        self.repo = SQLAlchemyProductRepository(session)

    async def get_products(self, category: str, query: Optional[str] = None) -> List[Product]:
        logger.info("LocalCatalogProvider retrieving products", category=category)
        products = await self.repo.get_by_category(category)
        
        # Exclude blacklisted products (e.g., OnePlus Nord 4 as requested by the user because it is not available)
        blacklist = ["nord 4", "nord4", "nord-4"]
        filtered_products = []
        for p in products:
            name_lower = p.name.lower()
            sku_lower = p.sku.lower()
            if any(b in name_lower or b in sku_lower for b in blacklist):
                logger.info("Excluding blacklisted product from catalog", name=p.name, sku=p.sku)
                continue
            filtered_products.append(p)
        return filtered_products


# ==========================================
# FUTURE EXPANSION SEARCH PROVIDER STUBS
# ==========================================

class GoogleShoppingProvider(CatalogProvider):
    """Retrieves real-time catalog prices and links from Google Shopping API."""

    async def get_products(self, category: str, query: Optional[str] = None) -> List[Product]:
        logger.warning("GoogleShoppingProvider is not implemented yet.")
        raise NotImplementedError("GoogleShoppingProvider integration is planned for a future release.")


class AmazonProvider(CatalogProvider):
    """Retrieves current listings, ratings, and stocks from Amazon PA-API."""

    async def get_products(self, category: str, query: Optional[str] = None) -> List[Product]:
        logger.warning("AmazonProvider is not implemented yet.")
        raise NotImplementedError("AmazonProvider integration is planned for a future release.")


class FlipkartProvider(CatalogProvider):
    """Retrieves localized Indian retail listings and availability from Flipkart API."""

    async def get_products(self, category: str, query: Optional[str] = None) -> List[Product]:
        logger.warning("FlipkartProvider is not implemented yet.")
        raise NotImplementedError("FlipkartProvider integration is planned for a future release.")


class BestBuyProvider(CatalogProvider):
    """Retrieves electronics pricing and specifications from BestBuy developer API."""

    async def get_products(self, category: str, query: Optional[str] = None) -> List[Product]:
        logger.warning("BestBuyProvider is not implemented yet.")
        raise NotImplementedError("BestBuyProvider integration is planned for a future release.")


class NotebookCheckProvider(CatalogProvider):
    """Retrieves detailed thermal benchmarks, FPS testing, and display charts for laptops."""

    async def get_products(self, category: str, query: Optional[str] = None) -> List[Product]:
        logger.warning("NotebookCheckProvider is not implemented yet.")
        raise NotImplementedError("NotebookCheckProvider integration is planned for a future release.")


class GSMArenaProvider(CatalogProvider):
    """Retrieves raw specifications and battery test scores for smartphones."""

    async def get_products(self, category: str, query: Optional[str] = None) -> List[Product]:
        logger.warning("GSMArenaProvider is not implemented yet.")
        raise NotImplementedError("GSMArenaProvider integration is planned for a future release.")


class RedditReviewProvider(CatalogProvider):
    """Gathers user discussions and known issues from subreddits (e.g. /r/SuggestALaptop)."""

    async def get_products(self, category: str, query: Optional[str] = None) -> List[Product]:
        logger.warning("RedditReviewProvider is not implemented yet.")
        raise NotImplementedError("RedditReviewProvider integration is planned for a future release.")
