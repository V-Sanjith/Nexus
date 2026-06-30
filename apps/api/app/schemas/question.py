from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

class QuestionSchema(BaseModel):
    id: UUID
    decision_id: UUID
    order_index: int
    question_text: str
    input_type: str
    options: Optional[dict] = None

    class Config:
        from_attributes = True

class QuestionListResponse(BaseModel):
    decision_id: UUID
    questions: List[QuestionSchema]
