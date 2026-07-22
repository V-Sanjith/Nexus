import asyncio
import sys
import os
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.user import User
from app.services.recommendation_service import RecommendationService
from app.services.category_registry import CategoryRegistry
from benchmark_v2.run_benchmark import run_scenario, SCENARIOS_TEST_FROZEN

async def debug_frozen_failures():
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    registry = CategoryRegistry()

    async with async_session_maker() as session:
        rec_service = RecommendationService(session)

        print("\n=================================================================")
        print("  FROZEN TEST DETAILED DISAGREEMENT AUDIT")
        print("=================================================================\n")

        for sc in SCENARIOS_TEST_FROZEN:
            r = await run_scenario(session, rec_service, sc, registry)
            status = "PASS" if r["winner_match"] else "DISAGREEMENT"
            print(f"[{status}] Scenario {sc['id']}: '{sc['name']}'")
            print(f"   Category: {sc['category']}, Budget: ₹{sc['budget']:,.0f}")
            print(f"   Expected: {sc.get('expected_winner')}")
            print(f"   Actual:   {r.get('winner') if 'winner' in r else 'N/A'}")
            print(f"   Regret:   {r['regret']:.4f}\n")

if __name__ == "__main__":
    asyncio.run(debug_frozen_failures())
