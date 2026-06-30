from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

class MessageSchema(BaseModel):
    id: UUID
    conversation_id: UUID
    sender: str # "USER", "NEXUS"
    content: str
    meta: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True

class MessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

class ConversationSchema(BaseModel):
    id: UUID
    decision_id: UUID
    user_id: UUID
    created_at: datetime
    messages: List[MessageSchema] = []

    class Config:
        from_attributes = True
