import asyncio
import sys
import os
import json
import logging
from uuid import uuid4
from sqlalchemy import select

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import async_session_maker
from app.models.user import User
from app.services.recommendation_service import RecommendationService
from app.services.category_registry import CategoryRegistry
from benchmark_v2.run_benchmark import run_scenario, SCENARIOS_VAL

async def test_val_diag():
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    registry = CategoryRegistry()

    async with async_session_maker() as session:
        user = (await session.execute(select(User).limit(1))).scalars().first()
        rec_service = RecommendationService(session)

        for sc in SCENARIOS_VAL:
            r = await run_scenario(session, rec_service, sc, registry)
            print("RUN SCENARIO RESULT FOR VAL_1:")
            print(json.dumps(r, indent=2))

if __name__ == "__main__":
    asyncio.run(test_val_diag())
