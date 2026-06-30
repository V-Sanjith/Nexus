import contextlib
from fastapi import FastAPI
from app.observability import configure_observability
from sqlalchemy import text
from app.db.session import engine, init_db, seed_database
import structlog

logger = structlog.get_logger()

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Observability and check databases
    configure_observability()
    logger.info("Initializing application startup sequence...")
    
    # Test DB engine connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection handshake verified.")
        
        # Initialize DB schema and seed tables
        await init_db()
        await seed_database()
        
        # Run Stage 4 catalog validation audit
        from app.db.session import async_session_maker
        from app.services.catalog_validator import CatalogValidator
        async with async_session_maker() as session:
            await CatalogValidator.validate_catalog(session)
    except Exception as e:
        logger.critical("Database connection/validation failed during startup!", error=str(e))
        raise e
        
    yield
    
    # Shutdown: Clean connection pools
    logger.info("Application shutdown triggered. Cleaning connection pools...")
    await engine.dispose()
    logger.info("Connection pools cleaned. Shutdown complete.")
