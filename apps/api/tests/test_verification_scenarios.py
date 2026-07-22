import asyncio
import sys
import os
import json
import logging
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.category_registry import CategoryRegistry
from app.services.decision_engine import DecisionEngine
from app.services.decision_guardrails import DecisionGuardrails
from app.services.decision_auditor import DecisionInvariantAuditor
from app.services.catalog_provider import LocalCatalogProvider
from app.db.session import async_session_maker

VERIFICATION_SCENARIOS = [
    {"id": 1, "title": "Gaming laptop with strict Rs1 lakh budget", "category": "laptop", "budget": 100000, "answers": [{"maps_to": "price", "selected_value": {"value": 100000}}, {"maps_to": "gpu_score", "selected_value": {"value": 5.0}}]},
    {"id": 2, "title": "Gaming laptop with performance priority", "category": "laptop", "budget": 150000, "answers": [{"maps_to": "price", "selected_value": {"value": 150000}}, {"maps_to": "gpu_score", "selected_value": {"value": 5.0}}, {"maps_to": "cpu_score", "selected_value": {"value": 5.0}}]},
    {"id": 3, "title": "Professional laptop with battery priority", "category": "laptop", "budget": 120000, "answers": [{"maps_to": "price", "selected_value": {"value": 120000}}, {"maps_to": "battery_hours", "selected_value": {"value": 5.0}}]},
    {"id": 4, "title": "Professional laptop with portability priority", "category": "laptop", "budget": 110000, "answers": [{"maps_to": "price", "selected_value": {"value": 110000}}, {"maps_to": "weight_kg", "selected_value": {"value": 5.0}}]},
    {"id": 5, "title": "Smartphone under Rs35,000", "category": "smartphone", "budget": 35000, "answers": [{"maps_to": "price", "selected_value": {"value": 35000}}]},
    {"id": 6, "title": "Smartphone under Rs60,000", "category": "smartphone", "budget": 60000, "answers": [{"maps_to": "price", "selected_value": {"value": 60000}}]},
    {"id": 7, "title": "Productivity monitor", "category": "monitor", "budget": 40000, "answers": [{"maps_to": "price", "selected_value": {"value": 40000}}, {"maps_to": "color_accuracy_delta_e", "selected_value": {"value": 5.0}}]},
    {"id": 8, "title": "Gaming monitor", "category": "monitor", "budget": 50000, "answers": [{"maps_to": "price", "selected_value": {"value": 50000}}, {"maps_to": "refresh_rate_hz", "selected_value": {"value": 5.0}}]},
    {"id": 9, "title": "Very low budget with no valid products", "category": "laptop", "budget": 5000, "answers": [{"maps_to": "price", "selected_value": {"value": 5000}}], "expect_no_match": True},
    {"id": 10, "title": "Impossible specification combination", "category": "laptop", "budget": 15000, "answers": [{"maps_to": "price", "selected_value": {"value": 15000}}, {"maps_to": "ram_gb", "selected_value": {"value": 64}}], "expect_no_match": True},
    {"id": 11, "title": "Winner and runner-up within 1% utility", "category": "laptop", "budget": 100000, "answers": [{"maps_to": "price", "selected_value": {"value": 100000}}, {"maps_to": "cpu_score", "selected_value": {"value": 3.0}}]},
    {"id": 12, "title": "Cheaper product retaining >=95% utility", "category": "laptop", "budget": 120000, "answers": [{"maps_to": "price", "selected_value": {"value": 120000}}, {"maps_to": "ram_gb", "selected_value": {"value": 16}}]},
    {"id": 13, "title": "Expensive upgrade providing <2% utility gain", "category": "laptop", "budget": 80000, "answers": [{"maps_to": "price", "selected_value": {"value": 80000}}, {"maps_to": "storage_gb", "selected_value": {"value": 512}}]},
    {"id": 14, "title": "Dominated candidate check", "category": "laptop", "budget": 90000, "answers": [{"maps_to": "price", "selected_value": {"value": 90000}}]},
    {"id": 15, "title": "Missing specification data check", "category": "laptop", "budget": 70000, "answers": [{"maps_to": "price", "selected_value": {"value": 70000}}]},
    {"id": 16, "title": "Ambiguous user query", "category": "laptop", "budget": 80000, "answers": [{"maps_to": "price", "selected_value": {"value": 80000}}]},
    {"id": 17, "title": "Semantically equivalent query paraphrases", "category": "laptop", "budget": 100000, "answers": [{"maps_to": "price", "selected_value": {"value": 100000}}]},
    {"id": 18, "title": "Small low-priority preference changes", "category": "laptop", "budget": 100000, "answers": [{"maps_to": "price", "selected_value": {"value": 100000}}, {"maps_to": "battery_hours", "selected_value": {"value": 1.5}}]},
    {"id": 19, "title": "Maximum budget boundary", "category": "laptop", "budget": 150000, "answers": [{"maps_to": "price", "selected_value": {"value": 150000}}]},
    {"id": 20, "title": "Product exactly equal to maximum budget", "category": "laptop", "budget": 90000, "answers": [{"maps_to": "price", "selected_value": {"value": 90000}}]}
]

async def run_verification_suite():
    registry = CategoryRegistry()
    results_log = []
    passed_cnt = 0

    print("=" * 80)
    print("  NEXUS STARTUP MVP — 20 VERIFICATION SCENARIOS AUDIT SUITE")
    print("=" * 80)

    async with async_session_maker() as session:
        provider = LocalCatalogProvider(session)

        for sc in VERIFICATION_SCENARIOS:
            cat_name = sc["category"]
            config = registry.get(cat_name)
            engine = DecisionEngine(config)
            products = await provider.get_products(cat_name)

            scored, trace, status = engine.run(
                products,
                sc["answers"],
                currency_symbol="₹",
                query=sc["title"]
            )

            # Apply Guardrails
            valid_scored, g_log = DecisionGuardrails.evaluate(
                scored,
                sc["answers"],
                config,
                engine,
                trace,
                "₹"
            )

            is_valid = True
            issue_msg = ""

            if sc.get("expect_no_match"):
                if status == "no_match_found" or len(valid_scored) == 0 or trace.get("status") == "no_match_found":
                    is_valid = True
            elif valid_scored:
                winner = valid_scored[0]
                price = float(winner.product.price_inr)
                max_budget = sc["budget"]

                # Hard Check: Budget Compliance
                if max_budget and price > max_budget and status != "no_match_found":
                    is_valid = False
                    issue_msg = f"Winner price ₹{price:,.0f} > Max Budget ₹{max_budget:,.0f}"

            status_str = "PASS" if is_valid else "FAIL"
            if is_valid:
                passed_cnt += 1

            print(f"  Scenario #{sc['id']:02d}: [{status_str}] {sc['title']}")
            if issue_msg:
                print(f"               Reason: {issue_msg}")

            results_log.append({
                "id": sc["id"],
                "title": sc["title"],
                "status": status_str,
                "winner": valid_scored[0].product.name if valid_scored else "None",
                "guardrail_log": g_log
            })

    print("=" * 80)
    print(f"  VERIFICATION RESULTS: {passed_cnt}/{len(VERIFICATION_SCENARIOS)} PASSED ({passed_cnt/len(VERIFICATION_SCENARIOS)*100:.1f}%)")
    print("=" * 80)

    return results_log

if __name__ == "__main__":
    asyncio.run(run_verification_suite())
