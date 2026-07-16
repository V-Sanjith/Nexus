from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DecisionStartRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200, description="Natural language description of what the user is looking for")
    category: Optional[str] = Field(default=None, description="Optional category override. If omitted, auto-detected from title.")
    currency: Optional[str] = Field(default="inr", description="Target currency for pricing inputs, e.g. 'inr'")

class IntentDetectRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200, description="The user's raw search query")

class IntentDetectResponse(BaseModel):
    category: str
    subcategory: str
    persona: str
    confidence: float
    questions_count: int

from app.schemas.question import QuestionSchema

class DecisionStartResponse(BaseModel):
    id: UUID
    user_id: UUID
    category: str
    subcategory: Optional[str] = None
    title: str
    status: str
    currency: str
    detected_use_case: Optional[str] = None
    intent_confidence: Optional[float] = None
    persona_weights: Optional[Dict[str, float]] = None
    version: int
    questions: List[QuestionSchema] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Keep backward compat alias
DecisionSchema = DecisionStartResponse
