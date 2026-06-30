from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.exceptions import NexusException
import structlog

logger = structlog.get_logger()

class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except NexusException as ne:
            # Catch known business validation/not found exceptions
            return JSONResponse(
                status_code=ne.status_code,
                content={
                    "error": {
                        "code": ne.code,
                        "message": ne.message,
                        "details": ne.details
                    }
                }
            )
        except Exception as e:
            # Catch raw unhandled server crashes, shielding database traces from the client
            logger.exception("Unhandled server crash", error=str(e))
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred. Reference trace logged."
                    }
                }
            )
