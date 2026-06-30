from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(tags=["Diagnostics"])

class HealthResponse(BaseModel):
    status: str
    version: str

@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """Diagnostic endpoint verifying API router viability."""
    return HealthResponse(status="healthy", version="0.1.0")
