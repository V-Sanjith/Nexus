import structlog
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.gemini import GeminiProvider
from app.models.product import Product
from sqlalchemy import select

logger = structlog.get_logger()

class CatalogEnricher:
    """Dynamically enriches the local catalog by searching the web for new products and real-time prices."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.provider = GeminiProvider()

    async def enrich_catalog(self, query: str, category: str, currency: str = "inr") -> int:
        """
        Searches the web for products matching the query in the given category,
        extracts their specifications and prices, and upserts them into the database.
        """
        logger.info("Enriching catalog with real-time web search", query=query, category=category, currency=currency)
        
        system_instruction = (
            "You are a precise e-commerce product scraper. Your job is to search the web using Google Search "
            "to find real, active, and available products matching the user's query.\n"
            "Only return products that are currently available for purchase (especially in the India region if currency is INR).\n"
            "Do not return fake or speculative products."
        )
        
        prompt = (
            f"User Query: \"{query}\"\n"
            f"Category: {category}\n"
            f"Target Currency: {currency.upper()}\n\n"
            "Instructions:\n"
            "1. Search the web for the top 5 most relevant and recently released models (or popular models) matching the query.\n"
            "2. For each product, find its actual current market price in the target region (e.g. India in INR).\n"
            "3. Convert the local price to USD using the rate: 1 USD = 98 INR (if price is in INR) or 1 USD = 1 USD (if in USD). Set this as 'price_inr'. This is extremely important so that when the app converts it back using 98 INR/USD, it matches the exact online price.\n"
            "4. Populate the 'specs' JSON object with valid, real specifications. Ensure it contains these keys:\n"
            f"   - For 'smartphone': camera_mp (number), battery_mah (number), screen_size (number), storage_gb (number), ram_gb (number), processor_score (number, 1000-10000), brand (string), phone_type (string, e.g. 'flagship', 'budget', 'midrange'), image_url (string, use a real unsplash or product image URL if possible, otherwise leave blank).\n"
            f"   - For 'laptop': ram_gb (number), storage_gb (number), weight_kg (number), battery_hours (number), cpu_score (number), gpu_score (number), screen_size (number), brand (string), laptop_type (string, e.g. 'gaming', 'business', 'student'), image_url (string).\n"
            f"   - For 'monitor': screen_size_inches (number), resolution_p (number, e.g. 1080, 1440, 2160), refresh_rate_hz (number), response_time_ms (number), color_accuracy_score (number, 1-10), panel_score (number, 1-10), brand (string), monitor_type (string, e.g. 'gaming', 'design'), image_url (string).\n"
            "5. Generate a unique, clean 'sku' string (lowercase, hyphenated, e.g. 'oneplus-nord-4-8-128').\n\n"
            "Return a JSON object with a single key 'products' containing a list of these products, matching the schema:\n"
            "{\n"
            "  \"products\": [\n"
            "    {\n"
            "      \"sku\": \"string\",\n"
            "      \"name\": \"string\",\n"
            "      \"price_inr\": number,\n"
            "      \"specs\": object\n"
            "    }\n"
            "  ]\n"
            "}"
        )
        
        try:
            result = await self.provider.generate_json(
                system_instruction=system_instruction,
                prompt=prompt,
                schema=None,
                enable_search=True
            )
            
            products_data = result.get("products", [])
            if not products_data:
                logger.info("No new products found during web search.")
                return 0
                
            logger.info(f"Found {len(products_data)} products online. Upserting to database...")
            
            upserted_count = 0
            for p_data in products_data:
                sku = p_data.get("sku")
                name = p_data.get("name")
                price_inr = p_data.get("price_inr")
                specs = p_data.get("specs", {})
                
                if not sku or not name or price_inr is None:
                    continue
                    
                sku = sku.lower().strip()
                name_lower = name.lower()
                
                # Skip blacklisted products (e.g., OnePlus Nord 4 as requested by the user because it is not available)
                blacklist = ["nord 4", "nord4", "nord-4"]
                if any(b in name_lower or b in sku for b in blacklist):
                    logger.info("Skipping blacklisted product from web search", name=name, sku=sku)
                    continue
                
                # Check if exists
                stmt = select(Product).where(Product.sku == sku)
                res = await self.session.execute(stmt)
                existing = res.scalars().first()
                
                if existing:
                    # Update price and specs
                    existing.price_inr = float(price_inr)
                    existing.name = name
                    
                    merged_specs = dict(existing.specs) if existing.specs else {}
                    merged_specs.update(specs)
                    existing.specs = merged_specs
                    
                    logger.info("Updated existing product price/specs", sku=sku, price_inr=price_inr)
                else:
                    # Create new
                    new_prod = Product(
                        sku=sku,
                        name=name,
                        category=category,
                        price_inr=float(price_inr),
                        specs=specs,
                        is_active=True
                    )
                    self.session.add(new_prod)
                    logger.info("Inserted new product from web search", sku=sku, price_inr=price_inr)
                    
                upserted_count += 1
                
            await self.session.flush()
            return upserted_count
            
        except Exception as e:
            logger.error("Catalog enrichment failed", error=str(e))
            return 0
