from uuid import UUID
from pydantic import BaseModel, Field

class ProductSchema(BaseModel):
    id: UUID
    sku: str
    name: str
    category: str
    price_inr: float
    specs: dict
    is_active: bool

    class Config:
        from_attributes = True

class ProductCreateRequest(BaseModel):
    sku: str = Field(..., min_length=3, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    category: str
    price_inr: float = Field(..., gt=0.0)
    specs: dict = Field(default_factory=dict)
