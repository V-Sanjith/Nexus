from typing import List
from uuid import UUID
from pydantic import BaseModel

class AnswerSubmission(BaseModel):
    question_id: UUID
    selected_value: dict

class AnswerSubmitRequest(BaseModel):
    answers: List[AnswerSubmission]

class AnswerSchema(BaseModel):
    id: UUID
    decision_id: UUID
    question_id: UUID
    selected_value: dict

    class Config:
        from_attributes = True
