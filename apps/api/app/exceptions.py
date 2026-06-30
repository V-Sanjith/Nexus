from typing import Any, Dict, Optional
from fastapi import HTTPException, status

class NexusException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationException(NexusException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="VALIDATION_FAILED",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details
        )

class EntityNotFoundException(NexusException):
    def __init__(self, entity_name: str, entity_id: str):
        super().__init__(
            code="ENTITY_NOT_FOUND",
            message=f"{entity_name} with ID {entity_id} not found.",
            status_code=status.HTTP_404_NOT_FOUND
        )
