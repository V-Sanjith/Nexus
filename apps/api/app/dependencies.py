from typing import AsyncGenerator, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.models.user import User
import structlog

logger = structlog.get_logger()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide db session dependency wrapper."""
    async for session in get_db_session():
        yield session

async def get_guest_user(
    x_guest_id: Optional[str] = Header(None, alias="X-Guest-ID"),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extracts guest UUID from request header, verifies DB profile,
    and seeds a temporary user record on demand to satisfy FK constraints.
    """
    if not x_guest_id:
        raise HTTPException(status_code=401, detail="Anonymous guest header 'X-Guest-ID' is required.")

    try:
        guest_uuid = UUID(x_guest_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Header 'X-Guest-ID' must be a valid UUID string.")

    # Fetch guest profile from database
    stmt = select(User).where(User.id == guest_uuid)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        logger.info("Initializing temporary guest profile record", guest_id=str(guest_uuid))
        user = User(
            id=guest_uuid,
            email=f"guest-{guest_uuid}@nexus.ai",
            password_hash="guest_session_key",
            is_deleted=False
        )
        db.add(user)
        await db.flush()

    return user
