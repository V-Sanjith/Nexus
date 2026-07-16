from datetime import datetime
from typing import List, Optional, Any
from uuid import UUID
from pydantic import BaseModel
from app.schemas.product import ProductSchema

class RecommendationVersionSchema(BaseModel):
    id: UUID
    recommendation_id: UUID
    version_index: int
    trigger_reason: str
    verdict_product_id: UUID
    confidence_score: float
    delta_analysis: dict
    created_at: datetime

    class Config:
        from_attributes = True

class RecommendationSchema(BaseModel):
    id: UUID
    decision_id: UUID
    verdict_product_id: UUID
    confidence_score: float
    structured_analysis: dict
    explanation_md: str
    created_at: datetime
    verdict_product: Optional[ProductSchema] = None
    versions: List[RecommendationVersionSchema] = []

    class Config:
        from_attributes = True

class StatelessAnswerInput(BaseModel):
    question_id: int
    selected_value: Any

class StatelessRecommendRequest(BaseModel):
    category: str
    subcategory: str = "general"
    persona: str = "general"
    currency: str = "inr"
    answers: List[StatelessAnswerInput]

