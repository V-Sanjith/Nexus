import sys
import io

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeError in console logging/printing
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.constants import APP_NAME
from app.lifespan import lifespan
from app.middleware import GlobalExceptionMiddleware
from app.observability.middleware import ObservabilityMiddleware
from app.routers import health, decision

app = FastAPI(
    title=APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV != "production" else None,
    redoc_url=None
)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Operational Middleware
app.add_middleware(GlobalExceptionMiddleware)
app.add_middleware(ObservabilityMiddleware)

# Mount Diagnostic routers
app.include_router(health.router)
app.include_router(decision.router)
