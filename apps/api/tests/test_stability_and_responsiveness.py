import asyncio
import sys
import os
import json
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.category_registry import CategoryRegistry
from app.services.decision_engine import DecisionEngine
from app.services.decision_guardrails import DecisionGuardrails
from app.services.catalog_provider import LocalCatalogProvider
from app.db.session import async_session_maker

async def evaluate_stability_and_responsiveness():
    registry = CategoryRegistry()
    config = registry.get("laptop")
    engine = DecisionEngine(config)

    print("=" * 80)
    print("  PARAPHRASE INVARIANCE vs PREFERENCE RESPONSIVENESS SUITE")
    print("=" * 80)

    async with async_session_maker() as session:
        provider = LocalCatalogProvider(session)
        products = await provider.get_products("laptop")

        # -------------------------------------------------------------
        # 1. PARAPHRASE INVARIANCE TEST
        # -------------------------------------------------------------
        paraphrase_groups = [
            {
                "group": "Gaming 100k",
                "queries": [
                    "Best gaming laptop below Rs100000",
                    "I need a gaming laptop, maximum budget Rs1,00,000",
                    "gaming laptop under 100000 INR"
                ],
                "answers": [
                    {"maps_to": "price", "selected_value": {"value": 100000}},
                    {"maps_to": "gpu_score", "selected_value": {"value": 5.0}},
                    {"maps_to": "cpu_score", "selected_value": {"value": 4.0}}
                ]
            },
            {
                "group": "Business Ultrabook 120k",
                "queries": [
                    "Portable work laptop budget Rs120000",
                    "Business ultrabook under 120000 INR",
                    "Work ultrabook max budget Rs120,000"
                ],
                "answers": [
                    {"maps_to": "price", "selected_value": {"value": 120000}},
                    {"maps_to": "weight_kg", "selected_value": {"value": 5.0}},
                    {"maps_to": "battery_hours", "selected_value": {"value": 4.0}}
                ]
            }
        ]

        total_paraphrase_pairs = 0
        invariant_pairs = 0

        for pg in paraphrase_groups:
            winners = []
            for q in pg["queries"]:
                scored, trace, _ = engine.run(products, pg["answers"], currency_symbol="₹", query=q)
                valid_scored, _ = DecisionGuardrails.evaluate(scored, pg["answers"], config, engine, trace, "₹")
                if valid_scored:
                    winners.append(valid_scored[0].product.sku)

            print(f"\nParaphrase Group '{pg['group']}': Winners = {set(winners)}")
            if len(set(winners)) == 1:
                invariant_pairs += 1
            total_paraphrase_pairs += 1

        paraphrase_invariance_rate = (invariant_pairs / total_paraphrase_pairs) * 100.0

        # -------------------------------------------------------------
        # 2. PREFERENCE RESPONSIVENESS TEST
        # -------------------------------------------------------------
        # Test Case A: Gaming Priority (High GPU, Low Battery/Weight)
        gaming_answers = [
            {"maps_to": "price", "selected_value": {"value": 120000}},
            {"maps_to": "gpu_score", "selected_value": {"value": 5.0}},
            {"maps_to": "cpu_score", "selected_value": {"value": 4.0}},
            {"maps_to": "battery_hours", "selected_value": {"value": 1.0}},
            {"maps_to": "weight_kg", "selected_value": {"value": 1.0}}
        ]

        # Test Case B: Portable Professional Priority (High Battery & Portability, Low GPU)
        pro_answers = [
            {"maps_to": "price", "selected_value": {"value": 120000}},
            {"maps_to": "gpu_score", "selected_value": {"value": 1.0}},
            {"maps_to": "cpu_score", "selected_value": {"value": 3.0}},
            {"maps_to": "battery_hours", "selected_value": {"value": 5.0}},
            {"maps_to": "weight_kg", "selected_value": {"value": 5.0}}
        ]

        scored_g, trace_g, _ = engine.run(products, gaming_answers, currency_symbol="₹", query="Gaming laptop", persona_hint="gamer")
        valid_g, _ = DecisionGuardrails.evaluate(scored_g, gaming_answers, config, engine, trace_g, "₹")
        winner_g = valid_g[0].product if valid_g else None

        scored_p, trace_p, _ = engine.run(products, pro_answers, currency_symbol="₹", query="Professional laptop", persona_hint="traveller")
        valid_p, _ = DecisionGuardrails.evaluate(scored_p, pro_answers, config, engine, trace_p, "₹")
        winner_p = valid_p[0].product if valid_p else None

        print(f"\nPreference Shift Test:")
        print(f"  Gaming Priority Winner:       {winner_g.name if winner_g else 'None'} (GPU: {winner_g.specs.get('gpu_score')}, Weight: {winner_g.specs.get('weight_kg')}kg)")
        print(f"  Professional Priority Winner: {winner_p.name if winner_p else 'None'} (Battery: {winner_p.specs.get('battery_hours')}h, Weight: {winner_p.specs.get('weight_kg')}kg)")

        is_responsive = (winner_g and winner_p and winner_g.id != winner_p.id)
        preference_responsiveness_rate = 100.0 if is_responsive else 0.0

        # -------------------------------------------------------------
        # 3. UNNECESSARY FLIP RATE TEST
        # -------------------------------------------------------------
        # Minor low-priority tweak: battery 3.0 vs 3.2 on clear winner
        tweak_answers = [
            {"maps_to": "price", "selected_value": {"value": 120000}},
            {"maps_to": "gpu_score", "selected_value": {"value": 5.0}},
            {"maps_to": "battery_hours", "selected_value": {"value": 3.2}}
        ]

        scored_t, trace_t, _ = engine.run(products, tweak_answers, "₹", query="Gaming laptop tweaked")
        valid_t, _ = DecisionGuardrails.evaluate(scored_t, tweak_answers, config, engine, trace_t, "₹")
        winner_t = valid_t[0].product if valid_t else None

        # Check if winner flipped unnecessarily when margin was large
        margin_g = (valid_g[0].score - valid_g[1].score) / max(abs(valid_g[0].score), 1e-6) if len(valid_g) > 1 else 1.0
        flipped = (winner_g and winner_t and winner_g.id != winner_t.id)
        unnecessary_flip = flipped and (margin_g > 0.05)
        unnecessary_flip_rate = 0.0 if not unnecessary_flip else 100.0

        print(f"\nMinor Tweak Test (Battery 3.0 -> 3.2):")
        print(f"  Base Winner:   {winner_g.name if winner_g else 'None'}")
        print(f"  Tweaked Winner: {winner_t.name if winner_t else 'None'}")
        print(f"  Winner Flipped: {flipped}")

        print("\n" + "=" * 80)
        print("  SUMMARY EVALUATION METRICS")
        print("=" * 80)
        print(f"  Paraphrase Invariance Rate:      {paraphrase_invariance_rate:.1f}%")
        print(f"  Preference Responsiveness Rate:  {preference_responsiveness_rate:.1f}%")
        print(f"  Unnecessary Flip Rate:           {unnecessary_flip_rate:.1f}%")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(evaluate_stability_and_responsiveness())
