from pydantic import BaseModel, Field
from typing import Optional, List, Tuple, Dict, Any
import structlog
from app.services.category_registry import CategoryRegistry

logger = structlog.get_logger()

class IntentResult(BaseModel):
    category: str
    subcategory: str
    persona: str
    confidence: float
    raw_title: str
    persona_weights: Optional[Dict[str, float]] = None

class IntentClassifier:
    """Keyword-first intent classifier with Gemini fallback for ambiguous inputs."""

    def __init__(self, registry: Optional[CategoryRegistry] = None):
        self.registry = registry or CategoryRegistry()

    async def classify(self, title: str) -> IntentResult:
        """
        Classify user input into category/subcategory/persona.
        Priority:
        1) Keyword-first matching (fast, deterministic)
        2) Gemini fallback (for ambiguous/complex inputs)
        """
        text = title.lower().strip()
        
        # 1. Try keyword matching first
        keyword_result = self.registry.match_keywords(text)
        if keyword_result:
            category, subcategory, persona = keyword_result
            logger.info("Intent classified via keywords", 
                        category=category, subcategory=subcategory, persona=persona)
            return IntentResult(
                category=category,
                subcategory=subcategory,
                persona=persona,
                confidence=95.0,
                raw_title=title,
                persona_weights=None # Predefined persona will load weights from YAML
            )
        
        # 2. Gemini fallback for ambiguous input
        try:
            return await self._classify_with_gemini(title)
        except Exception as e:
            logger.warning("Gemini classification failed, using default fallback", error=str(e))
            # Ultimate fallback: laptop/general
            return IntentResult(
                category="laptop",
                subcategory="general",
                persona="general",
                confidence=30.0,
                raw_title=title,
                persona_weights=None
            )

    async def _classify_with_gemini(self, title: str) -> IntentResult:
        """Use Gemini to classify ambiguous/complex user input."""
        from app.ai.gemini import GeminiProvider
        
        available = self.registry.list_categories()
        categories_str = ", ".join([c["key"] for c in available])
        
        # Build category attributes details for Gemini custom persona weights generation
        details = []
        for c in available:
            config = self.registry.get(c["key"])
            if config:
                sub_info = []
                for sub_name, sub_config in config.subcategories.items():
                    sub_info.append(f"{sub_name} (persona: {sub_config.default_persona}, keywords: {', '.join(sub_config.keywords)})")
                
                attrs_info = [f"{attr.key} ({attr.name}, type: {attr.type})" for attr in config.attributes if not attr.is_hard_filter]
                
                details.append(
                    f"- Category '{config.category}':\n"
                    f"  Subcategories: [{'; '.join(sub_info)}]\n"
                    f"  Soft Attributes: [{', '.join(attrs_info)}]\n"
                    f"  Predefined Personas: {list(config.personas.keys())}"
                )

        details_str = "\n".join(details)

        prompt = (
            f"Classify this user's natural language request into a product category, subcategory, and persona.\n"
            f"User request: \"{title}\"\n\n"
            f"Available categories and their details:\n{details_str}\n\n"
            f"Instructions:\n"
            f"1. Choose a category from: {categories_str}. If none fits perfectly, pick the closest one.\n"
            f"2. Choose a subcategory (use one of the subcategories listed for that category, or choose 'general' if not specific).\n"
            f"3. Detect the persona/use-case. You can select one of the predefined personas, OR you can synthesize an AI-generated custom persona if the user has a specialized need (e.g., 'Music Producer', 'CAD Designer', 'Financial Analyst', 'Mobile Vlogger').\n"
            f"4. If and only if you choose a custom persona (i.e. not in the predefined list), you must provide a dict of weight multipliers for the Soft Attributes of the chosen category. The weight multipliers should range between 0.5 (low importance) and 2.5 (extremely high importance). Keep normal/unmentioned attributes at 1.0. If you pick a predefined persona, you can leave persona_weights null.\n"
            f"5. Return confidence (0.0 to 100.0) based on how certain you are.\n\n"
            f"Return a JSON object conforming exactly to this structure:\n"
            f"{{\n"
            f"  \"category\": \"category_key\",\n"
            f"  \"subcategory\": \"subcategory_key\",\n"
            f"  \"persona\": \"persona_name\",\n"
            f"  \"confidence\": 85.0,\n"
            f"  \"persona_weights\": {{\"attribute_key\": 1.8, ...}} or null\n"
            f"}}"
        )
        
        provider = GeminiProvider()
        
        class ClassificationSchema(BaseModel):
            category: str
            subcategory: str = "general"
            persona: str = "general"
            confidence: float = 50.0
            persona_weights: Optional[Dict[str, float]] = None

        result_dict = await provider.generate_json(
            system_instruction="You are a product search intent classifier. Return only valid JSON.",
            prompt=prompt,
            schema=ClassificationSchema
        )
        
        category = result_dict.get("category", "laptop").lower().strip()
        subcategory = result_dict.get("subcategory", "general").lower().strip()
        persona = result_dict.get("persona", "general").lower().strip()
        confidence = float(result_dict.get("confidence", 50.0))
        persona_weights = result_dict.get("persona_weights")
        
        # Validate that category exists
        valid_keys = [c["key"] for c in available]
        if category not in valid_keys:
            category = "laptop"
            confidence = 30.0
            persona = "general"
            subcategory = "general"
            persona_weights = None

        config = self.registry.get(category)
        if config:
            # If predefined persona matches, use predefined and discard custom weights to be clean
            if persona in config.personas:
                persona_weights = None
            else:
                # Custom/AI-generated persona
                # Ensure persona_weights only contains valid soft attributes for this category
                valid_attrs = {attr.key for attr in config.attributes if not attr.is_hard_filter}
                if persona_weights:
                    filtered_weights = {}
                    for k, v in persona_weights.items():
                        if k in valid_attrs:
                            try:
                                filtered_weights[k] = float(v)
                            except ValueError:
                                continue
                    persona_weights = filtered_weights if filtered_weights else None

        return IntentResult(
            category=category,
            subcategory=subcategory,
            persona=persona,
            confidence=confidence,
            raw_title=title,
            persona_weights=persona_weights
        )
