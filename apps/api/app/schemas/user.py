from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

class UserProfileSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: dict = Field(default_factory=dict)

    class Config:
        from_attributes = True

class UserDecisionDNASchema(BaseModel):
    traits: dict = Field(default_factory=dict)
    last_calculated: datetime

    class Config:
        from_attributes = True

class UserSchema(BaseModel):
    id: UUID
    email: EmailStr
    profile: Optional[UserProfileSchema] = None
    dna: Optional[UserDecisionDNASchema] = None
    created_at: datetime

    class Config:
        from_attributes = True

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    access_token_expiry: int # Unix epoch timestamp
    user: UserSchema
