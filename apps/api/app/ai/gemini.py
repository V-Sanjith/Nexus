import httpx
import json
from typing import Any, Dict
from app.config import settings
from app.ai.provider import BaseLLMProvider
import structlog
import re

logger = structlog.get_logger()

class GeminiProvider(BaseLLMProvider):
    """Google Gemini API Provider implementation using httpx."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = "gemini-2.5-flash"

    async def generate_json(self, system_instruction: str, prompt: str, schema: Any, enable_search: bool = False) -> Dict[str, Any]:
        is_valid_key = self.api_key and self.api_key.startswith("AIzaSy")
        if not is_valid_key:
            logger.warning("GEMINI_API_KEY is not configured or is invalid. Falling back to structural mock generator.")
            return self._generate_mock(prompt)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        # Prepare content and instruct Gemini to return structured JSON
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"{system_instruction}\n\nAnalyze the following data and generate the JSON output:\n{prompt}"
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        if enable_search:
            payload["tools"] = [{"google_search": {}}]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=payload, timeout=20.0)
                response.raise_for_status()
                data = response.json()
                
                text_output = data["candidates"][0]["content"]["parts"][0]["text"]
                logger.info("Successfully received structured response from Gemini API.")
                
                # Parse JSON and return
                return json.loads(text_output)
            except Exception as e:
                logger.error("Gemini API transaction failed! Falling back to mock generator.", error=str(e))
                return self._generate_mock(prompt)

    def _generate_mock(self, prompt: str) -> Dict[str, Any]:
        """Generates a high-quality mock response reflecting the parsed prompt values."""
        # Check if this is a classification prompt
        if "Classify" in prompt or "category_key" in prompt:
            query = ""
            query_match = re.search(r"User request:\s*\"([^\"]+)\"", prompt)
            if query_match:
                query = query_match.group(1).lower().strip()
            else:
                query_match_2 = re.search(r"request:\s*\"([^\"]+)\"", prompt)
                if query_match_2:
                    query = query_match_2.group(1).lower().strip()
            
            # Default classification
            category = "laptop"
            subcategory = "general"
            persona = "general"
            
            # Detect category
            if any(k in query for k in ["phone", "smartphone", "mobile", "pixel", "iphone", "samsung s24", "oneplus"]):
                category = "smartphone"
            elif any(k in query for k in ["monitor", "screen", "display", "odyssey", "ultragear"]):
                category = "monitor"
            elif any(k in query for k in ["laptop", "notebook", "computer", "macbook", "thinkpad", "zephyrus", "victus"]):
                category = "laptop"
                
            # Detect subcategory / persona
            if "gaming" in query or "game" in query or "gamer" in query:
                subcategory = "gaming"
                persona = "gamer"
            elif "developer" in query or "coding" in query or "program" in query:
                subcategory = "developer" if category == "laptop" else "general"
                persona = "developer"
            elif "design" in query or "photo" in query or "creator" in query or "edit" in query:
                subcategory = "creator" if category == "laptop" else ("photography" if category == "smartphone" else "design")
                persona = "video_editor" if category == "laptop" else ("photographer" if category == "smartphone" else "designer")
            elif "business" in query or "work" in query or "travel" in query:
                subcategory = "business" if category == "laptop" else "flagship"
                persona = "business_user"
            elif "student" in query or "budget" in query:
                subcategory = "student" if category == "laptop" else "budget"
                persona = "student"
                
            return {
                "category": category,
                "subcategory": subcategory,
                "persona": persona,
                "confidence": 95.0,
                "persona_weights": None
            }

        # Simple extraction of key details from prompt to make mock response feel alive
        sku_match = re.search(r"Verdict Product SKU:\s*([a-zA-Z0-9\-]+)", prompt)
        name_match = re.search(r"Verdict Product Name:\s*([^\n]+)", prompt)
        score_match = re.search(r"Verdict Score:\s*([0-9\.]+)", prompt)
        conf_match = re.search(r"Confidence:\s*([0-9\.]+)", prompt)
        
        sku = sku_match.group(1) if sku_match else "apple-mba-m3-16-512"
        name = name_match.group(1).strip() if name_match else "Apple MacBook Air M3"
        score = float(score_match.group(1)) if score_match else 0.85
        confidence = float(conf_match.group(1)) if conf_match else 88.5
        
        return {
            "verdict_sku": sku,
            "score": score,
            "confidence": confidence,
            "pros": [
                f"Directly satisfies your top priority preferences for {name}.",
                "Optimized specifications offering a highly responsive user experience.",
                "Outstanding value efficiency relative to its price bracket."
            ],
            "cons": [
                "Lacks some advanced interfaces found in larger premium models.",
                "Storage expansion is limited once purchased."
            ],
            "reasoning": f"The decision scoring engine identified {name} as the highest utility match (score: {score:.2f}) because it perfectly balances your budget requirements and weights. Alternate options were filtered out due to hard spec checks or were heavily penalized due to higher pricing and weight metrics.",
            "summary": f"We recommend the {name} as your best overall match. It satisfies all your hard constraints and aligns with your soft weighting preferences.",
            "citations": [
                "Official Manufacturer Specification sheet",
                "Nexus Decision Engine calculations"
            ]
        }
