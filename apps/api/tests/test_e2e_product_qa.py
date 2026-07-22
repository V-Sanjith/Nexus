import asyncio
import sys
import os
import time
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.product import Product
from app.services.recommendation_service import RecommendationService
from app.services.category_registry import CategoryRegistry
from app.schemas.recommendation import StatelessRecommendRequest, StatelessAnswerInput

CROSS_CATEGORY_SCENARIOS = [
    {"name": "Low-budget laptop", "category": "laptop", "subcategory": "general", "budget": 60000},
    {"name": "Mid-range laptop", "category": "laptop", "subcategory": "gaming", "budget": 85000},
    {"name": "Premium laptop", "category": "laptop", "subcategory": "creator", "budget": 180000},
    {"name": "Low-budget smartphone", "category": "smartphone", "subcategory": "budget", "budget": 25000},
    {"name": "Mid-range smartphone", "category": "smartphone", "subcategory": "photography", "budget": 45000},
    {"name": "Premium smartphone", "category": "smartphone", "subcategory": "flagship", "budget": 95000},
    {"name": "Budget monitor", "category": "monitor", "subcategory": "productivity", "budget": 18000},
    {"name": "Gaming monitor", "category": "monitor", "subcategory": "gaming", "budget": 25000},
    {"name": "Productivity monitor", "category": "monitor", "subcategory": "designer", "budget": 45000},
]

async def run_e2e_qa_audit():
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    registry = CategoryRegistry()

    latencies = []
    matrix_results = []

    print("\n==========================================================================================")
    print("  NEXUS FULL END-TO-END QA, DATA INTEGRITY & CROSS-CATEGORY PARITY AUDIT")
    print("==========================================================================================\n")

    async with async_session_maker() as session:
        rec_service = RecommendationService(session)

        for sc in CROSS_CATEGORY_SCENARIOS:
            t0 = time.perf_counter()
            if sc["category"] == "laptop":
                answers = [
                    StatelessAnswerInput(question_id=1, selected_value={"value": sc["budget"]}),
                    StatelessAnswerInput(question_id=2, selected_value={"value": 8}),
                    StatelessAnswerInput(question_id=3, selected_value={"value": 256}),
                    StatelessAnswerInput(question_id=4, selected_value={"value": 3.0}),
                    StatelessAnswerInput(question_id=5, selected_value={"value": 3.0})
                ]
            elif sc["category"] == "smartphone":
                answers = [
                    StatelessAnswerInput(question_id=1, selected_value={"value": sc["budget"]}),
                    StatelessAnswerInput(question_id=2, selected_value={"value": 3.0}),
                    StatelessAnswerInput(question_id=3, selected_value={"value": 3.0}),
                    StatelessAnswerInput(question_id=4, selected_value={"value": 6.4}),
                    StatelessAnswerInput(question_id=5, selected_value={"value": 128})
                ]
            else:  # monitor
                answers = [
                    StatelessAnswerInput(question_id=1, selected_value={"value": sc["budget"]}),
                    StatelessAnswerInput(question_id=2, selected_value={"value": 3.0}),
                    StatelessAnswerInput(question_id=3, selected_value={"value": 3.0}),
                    StatelessAnswerInput(question_id=4, selected_value={"value": 27})
                ]

            payload = StatelessRecommendRequest(
                category=sc["category"],
                subcategory=sc["subcategory"],
                persona="general",
                answers=answers,
                currency="inr"
            )

            res = await rec_service.generate_recommendation_stateless(payload)
            elapsed_s = time.perf_counter() - t0
            latencies.append(elapsed_s)

            # Feature Parity Check
            sa = res.get("structured_analysis") or res
            print("  [DEBUG KEYS]", list(res.keys()), "-> sa keys:", list(sa.keys()) if isinstance(sa, dict) else None)
            winner = res.get("verdict_product") or sa.get("verdict_product")
            winner_ok = winner is not None
            runner_ok = res.get("runner_up") is not None or sa.get("battle_comparison") is not None
            battle_ok = sa.get("battle_comparison") is not None
            spend_less_ok = sa.get("spend_less_analysis") is not None
            upgrade_ok = sa.get("upgrade_analysis") is not None and sa.get("upgrade_analysis", {}).get("status") in ["upgrade_recommended", "not_worth_upgrading", "no_upgrade_available"]
            marginal_ok = sa.get("upgrade_analysis") is not None
            sensitivity_ok = sa.get("sensitivity_analysis") is not None or sa.get("tradeoffs") is not None
            reliability_ok = sa.get("reliability_score") is not None or res.get("confidence") is not None
            best_avoid_ok = sa.get("pros") is not None and sa.get("cons") is not None

            img_prov = sa.get("image_provenance") or (winner.get("image_provenance") if winner else None) or RecommendationService._determine_image_provenance(winner)
            img_ok = img_prov is not None and img_prov.get("image_match_level") in ["exact_variant", "exact_model", "product_family", "unavailable"]

            matrix_results.append({
                "Scenario": sc["name"],
                "Category": sc["category"],
                "Winner": "PASS" if winner_ok else "FAIL",
                "RunnerUp": "PASS" if runner_ok else "FAIL",
                "BattleCard": "PASS" if battle_ok else "FAIL",
                "SpendLess": "PASS" if spend_less_ok else "FAIL",
                "UpgradeAnalysis": "PASS" if upgrade_ok else "FAIL",
                "MarginalUpgrade": "PASS" if marginal_ok else "FAIL",
                "Sensitivity": "PASS" if sensitivity_ok else "FAIL",
                "Reliability": "PASS" if reliability_ok else "FAIL",
                "BestForAvoid": "PASS" if best_avoid_ok else "FAIL",
                "ImageProvenance": "PASS" if img_ok else "FAIL",
                "LatencySec": f"{elapsed_s:.2f}s"
            })

            print(f"[{'PASS' if winner_ok and upgrade_ok else 'FAIL'}] {sc['name']} ({sc['category']}): Winner = {winner.get('name') if winner else 'None'} | Upgrade Status = {res.get('upgrade_analysis', {}).get('status')} | Latency = {elapsed_s:.2f}s")

    latencies.sort()
    p50 = latencies[len(latencies)//2]
    p95 = latencies[int(len(latencies)*0.95)]

    print("\n==========================================================================================")
    print("  CROSS-CATEGORY FEATURE PARITY VERIFICATION MATRIX")
    print("==========================================================================================")
    print(f"{'Scenario':<25} | {'Winner':<6} | {'RunnerUp':<8} | {'Battle':<6} | {'SpendLess':<9} | {'Upgrade':<7} | {'Latency':<7}")
    print("-" * 80)
    for row in matrix_results:
        print(f"{row['Scenario']:<25} | {row['Winner']:<6} | {row['RunnerUp']:<8} | {row['BattleCard']:<6} | {row['SpendLess']:<9} | {row['UpgradeAnalysis']:<7} | {row['LatencySec']:<7}")

    print("\n==========================================================================================")
    print("  PERFORMANCE LATENCY SUMMARY")
    print("==========================================================================================")
    print(f"  p50 Latency: {p50:.2f}s (Target: < 2.0s) -> {'PASS' if p50 < 2.0 else 'FAIL'}")
    print(f"  p95 Latency: {p95:.2f}s (Target: < 4.0s) -> {'PASS' if p95 < 4.0 else 'FAIL'}")
    print("==========================================================================================\n")

if __name__ == "__main__":
    asyncio.run(run_e2e_qa_audit())
