from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class PromptContext(BaseModel):
    """Context parameters passed to the Prompt Builder."""
    category: str
    user_email: str
    decision_title: str
    answers_summary: List[Dict[str, Any]]
    verdict_product: Dict[str, Any]
    verdict_score: float
    confidence_score: float
    alternatives: List[Dict[str, Any]]
    tradeoffs: List[Dict[str, Any]]

class StructuredRecommendation(BaseModel):
    """Strict output schema expected from the LLM provider."""
    verdict_sku: str = Field(..., description="The SKU of the recommended product")
    score: float = Field(..., description="The mathematical utility score of the product")
    confidence: float = Field(..., description="The calculated confidence score (0 to 100)")
    pros: List[str] = Field(..., description="Key strengths of the recommended product matching the user's specific answers")
    cons: List[str] = Field(..., description="Limitations or drawbacks of the recommended product relative to user expectations")
    reasoning: str = Field(..., description="Detailed, logical explanation of why this product won over the alternatives based on MCDA math")
    summary: str = Field(..., description="A friendly, conversational 2-sentence summary of the recommendation verdict")
    citations: List[str] = Field(..., description="List of source links or specs verification references cited")
