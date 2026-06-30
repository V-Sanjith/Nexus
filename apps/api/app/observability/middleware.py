import time
import uuid
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.constants import CORRELATION_ID_HEADER
from app.observability.metrics import http_requests_total, http_request_duration_seconds

logger = structlog.get_logger()

class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        
        # Clear/bind variables to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=correlation_id,
            method=request.method,
            path=request.url.path
        )

        start_time = time.perf_counter()
        
        try:
            response: Response = await call_next(request)
            duration = time.perf_counter() - start_time
            
            # Record Prometheus metrics
            http_requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            # Log structured performance log
            logger.info(
                "Request processed successfully",
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2)
            )
            
            # Inject Correlation ID into response headers
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response
            
        except Exception as e:
            duration = time.perf_counter() - start_time
            http_requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status=500
            ).inc()
            logger.error(
                "Exception occurred while processing request",
                error=str(e),
                duration_ms=round(duration * 1000, 2)
            )
            raise e
