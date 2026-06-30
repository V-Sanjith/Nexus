from typing import Dict, Any
from app.ai.schemas import StructuredRecommendation

class OutputParser:
    """Parses and validates LLM provider outputs against target Pydantic schemas."""

    @staticmethod
    def parse_recommendation(data: Dict[str, Any]) -> StructuredRecommendation:
        """Validates and returns the structured recommendation model."""
        return StructuredRecommendation.model_validate(data)
