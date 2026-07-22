import asyncio
import sys
import os
import time
import json
import logging
from uuid import uuid4
from typing import List, Dict, Any

# Suppress SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Add python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from app.db.session import async_session_maker, engine
from app.models.user import User
from app.models.product import Product
from app.models.decision import Decision
from app.models.question import Question
from app.models.answer import Answer
from app.services.recommendation_service import RecommendationService
from app.services.category_registry import CategoryRegistry

SCENARIOS_DEV = [
    {
        "id": "dev_1",
        "name": "Standard Laptop under 1 Lakh",
        "category": "laptop",
        "subcategory": "general",
        "budget": 100000.0,
        "answers": {"ram_gb": 16, "storage_gb": 512, "cpu_score": 3, "gpu_score": 2, "battery_hours": 4, "weight_kg": 3},
        "expected_winner": ["Lenovo LOQ", "ASUS TUF", "Acer Nitro"]
    },
    {
        "id": "dev_2",
        "name": "Gaming Laptop under 1.5 Lakh",
        "category": "laptop",
        "subcategory": "general",
        "budget": 150000.0,
        "answers": {"ram_gb": 16, "storage_gb": 1024, "cpu_score": 5, "gpu_score": 5, "battery_hours": 2, "weight_kg": 1},
        "expected_winner": ["ROG Zephyrus", "Lenovo Legion"]
    }
]

SCENARIOS_VAL = [
    {
        "id": "val_1",
        "name": "Premium Camera Phone",
        "category": "smartphone",
        "subcategory": "general",
        "budget": 120000.0,
        "answers": {"ram_gb": 12, "storage_gb": 256, "camera_mp": 5, "battery_mah": 3, "screen_size": 3, "processor_score": 4},
        "expected_winner": ["Galaxy S25", "iPhone", "Pixel"]
    }
]

SCENARIOS_TEST_FROZEN = [
    {
        "id": "test_1",
        "name": "Adversarial: Extremely Low Laptop Budget (Rs 20,000)",
        "category": "laptop",
        "subcategory": "general",
        "budget": 20000.0,
        "answers": {"ram_gb": 8, "storage_gb": 256},
        "expected_winner": None
    },
    {
        "id": "test_2",
        "name": "Adversarial: Extremely High Laptop Budget (Rs 5,000,000)",
        "category": "laptop",
        "subcategory": "general",
        "budget": 5000000.0,
        "answers": {"ram_gb": 16, "storage_gb": 512},
        "expected_winner": "ANY_MATCH"
    },
    {
        "id": "test_3",
        "name": "Budget Phone under Rs 15,000",
        "category": "smartphone",
        "subcategory": "general",
        "budget": 15000.0,
        "answers": {"ram_gb": 6, "storage_gb": 128},
        "expected_winner": "ANY_MATCH"
    },
    {
        "id": "test_4",
        "name": "Adversarial: Near budget boundary (Rs 80,000 Gaming Laptop)",
        "category": "laptop",
        "subcategory": "general",
        "budget": 80000.0,
        "answers": {"ram_gb": 16, "storage_gb": 512, "gpu_score": 4},
        "expected_winner": "ANY_MATCH"
    },
    {
        "id": "test_5",
        "name": "Business Laptop under Rs 60,000",
        "category": "laptop",
        "subcategory": "general",
        "budget": 60000.0,
        "answers": {"ram_gb": 8, "storage_gb": 256, "battery_hours": 5, "weight_kg": 5, "cpu_score": 3, "gpu_score": 1},
        "expected_winner": "ANY_MATCH"
    },
    {
        "id": "test_6",
        "name": "Mid-range Phone under Rs 35,000",
        "category": "smartphone",
        "subcategory": "general",
        "budget": 35000.0,
        "answers": {"ram_gb": 8, "storage_gb": 128, "camera_mp": 3, "battery_mah": 4, "processor_score": 3},
        "expected_winner": "ANY_MATCH"
    }
]


async def run_scenario(session, rec_service, sc, registry):
    """Runs a single scenario and returns metrics dict."""
    decision_id = uuid4()
    decision = Decision(
        id=decision_id,
        user_id=(await session.execute(select(User).limit(1))).scalars().first().id,
        title=f"Benchmark V2 {sc['id']}",
        category=sc["category"],
        subcategory=sc["subcategory"],
        status="QUESTIONING",
        currency="inr",
        detected_use_case="general",
        intent_confidence=95.0
    )
    session.add(decision)
    await session.flush()

    config = registry.get(sc["category"], sc["subcategory"])
    questions = config.questions if hasattr(config, "questions") else []

    for idx, q_def in enumerate(questions):
        q_text = getattr(q_def, "question_text", "")
        maps_to = getattr(q_def, "maps_to", "")
        input_type = getattr(q_def, "input_type", "")

        q_id = uuid4()
        db_q = Question(
            id=q_id,
            decision_id=decision_id,
            order_index=idx + 1,
            question_text=q_text,
            input_type=input_type,
            options={"maps_to": maps_to} if maps_to else None,
            weight_impact={"maps_to": maps_to} if maps_to else None
        )
        session.add(db_q)
        await session.flush()

        selected_val = None
        if maps_to == "price":
            selected_val = {"value": sc["budget"]}
        elif maps_to in sc["answers"]:
            selected_val = {"value": sc["answers"][maps_to]}
        elif input_type == "slider":
            selected_val = {"value": 3.0}
        elif input_type == "single_choice":
            opts = getattr(q_def, "options", None)
            choices = []
            if opts and hasattr(opts, "choices"):
                choices = opts.choices
            elif isinstance(opts, dict):
                choices = opts.get("choices", [])
            selected_val = {"value": choices[0] if choices else 16}

        if selected_val is not None:
            db_ans = Answer(
                decision_id=decision_id,
                question_id=q_id,
                selected_value=selected_val
            )
            session.add(db_ans)

    await session.flush()
    await session.commit()

    result = {
        "id": sc["id"],
        "name": sc["name"],
        "passed": False,
        "budget_compliant": False,
        "hard_compliant": False,
        "stable": False,
        "regret": 0.0,
        "latency_ms": 0.0,
        "winner_match": False,
        "error": None
    }

    t_start = time.perf_counter()
    try:
        rec = await rec_service.generate_recommendation(decision_id)
        await session.commit()
        result["latency_ms"] = (time.perf_counter() - t_start) * 1000.0

        sa = rec.structured_analysis or {}
        vp = rec.verdict_product

        # Budget compliance
        if vp:
            price_inr = float(vp.price_inr)
            result["budget_compliant"] = price_inr <= sc["budget"]
        else:
            result["budget_compliant"] = True  # no_match is budget-compliant

        # Hard constraint compliance
        result["hard_compliant"] = True
        if vp:
            for k, req_v in sc["answers"].items():
                if k in ["ram_gb", "storage_gb"]:
                    spec_v = vp.specs.get(k, 0)
                    if spec_v and spec_v < req_v:
                        result["hard_compliant"] = False

        # Stability
        rb = sa.get("reliability_breakdown", {})
        result["stable"] = rb.get("stability_score", 100.0) == 100.0

        # Regret
        ranking = sa.get("decision_trace", {}).get("ranking", [])
        if ranking and vp:
            top_score = ranking[0].get("score", 1.0)
            winner_score = next((r["score"] for r in ranking if r.get("sku") == vp.sku), top_score)
            result["regret"] = max(0.0, top_score - winner_score)

        # Winner match
        expected = sc.get("expected_winner")
        if expected is None:
            result["winner_match"] = vp is None
        elif expected == "ANY_MATCH":
            result["winner_match"] = vp is not None
        elif isinstance(expected, list):
            result["winner_match"] = vp is not None and any(e.lower() in vp.name.lower() for e in expected)
        else:
            result["winner_match"] = vp is not None and expected.lower() in vp.name.lower()

        result["passed"] = True

    except Exception as e:
        result["error"] = str(e)
    finally:
        await session.execute(delete(Answer).where(Answer.decision_id == decision_id))
        await session.execute(delete(Question).where(Question.decision_id == decision_id))
        await session.execute(delete(Decision).where(Decision.id == decision_id))
        await session.commit()

    return result


async def run_scenario_suite(suite_name, scenarios):
    print(f"\n{'='*60}")
    print(f"  SUITE: {suite_name.upper()}")
    print(f"{'='*60}")

    results = []
    registry = CategoryRegistry()

    async with async_session_maker() as session:
        # Ensure user exists
        user = (await session.execute(select(User).limit(1))).scalars().first()
        if not user:
            user = User(id=uuid4(), email="benchmark_v2@nexus.ai", password_hash="hash")
            session.add(user)
            await session.commit()

        rec_service = RecommendationService(session)

        for sc in scenarios:
            print(f"\n  [{sc['id']}] {sc['name']}")
            r = await run_scenario(session, rec_service, sc, registry)
            results.append(r)

            if r["error"]:
                print(f"    -> ERROR: {r['error']}")
            else:
                status = "PASS" if r["winner_match"] else "MISS"
                print(f"    -> [{status}] Budget OK: {r['budget_compliant']}, Hard OK: {r['hard_compliant']}, Stable: {r['stable']}, Regret: {r['regret']:.4f}, Latency: {r['latency_ms']:.0f}ms")

    # Aggregate
    executed = [r for r in results if r["passed"]]
    n = len(executed)
    if n == 0:
        print(f"\n  All {len(scenarios)} scenarios ERRORED.")
        return {"suite": suite_name, "total": len(scenarios), "executed": 0}

    top1_pct = sum(1 for r in executed if r["winner_match"]) / len(scenarios) * 100
    budget_pct = sum(1 for r in executed if r["budget_compliant"]) / n * 100
    hard_pct = sum(1 for r in executed if r["hard_compliant"]) / n * 100
    stability_pct = sum(1 for r in executed if r["stable"]) / n * 100
    avg_regret = sum(r["regret"] for r in executed) / n
    avg_latency = sum(r["latency_ms"] for r in executed) / n

    summary = {
        "suite": suite_name,
        "total": len(scenarios),
        "executed": n,
        "top1_agreement": round(top1_pct, 1),
        "budget_compliance": round(budget_pct, 1),
        "hard_compliance": round(hard_pct, 1),
        "stability": round(stability_pct, 1),
        "avg_regret": round(avg_regret, 4),
        "avg_latency_ms": round(avg_latency, 1)
    }

    print(f"\n  Suite Summary:")
    print(f"    Executed: {n}/{len(scenarios)}")
    print(f"    Top-1 Agreement: {top1_pct:.1f}%")
    print(f"    Budget Compliance: {budget_pct:.1f}%")
    print(f"    Hard Constraint Compliance: {hard_pct:.1f}%")
    print(f"    Recommendation Stability: {stability_pct:.1f}%")
    print(f"    Average Decision Regret: {avg_regret:.4f}")
    print(f"    Average Latency: {avg_latency:.0f}ms")

    return summary


import argparse
from datetime import datetime

async def main():
    parser = argparse.ArgumentParser(description="Nexus Benchmark V2 Runner")
    parser.add_argument("--split", choices=["dev", "val", "frozen", "all"], default="all", help="Dataset split to evaluate")
    args = parser.parse_args()

    os.makedirs("tests/benchmark_v2/runs", exist_ok=True)
    
    # Save frozen scenarios safely without overwriting if already exists
    with open("tests/benchmark_v2/scenarios_dev.json", "w") as f:
        json.dump(SCENARIOS_DEV, f, indent=2)
    with open("tests/benchmark_v2/scenarios_val.json", "w") as f:
        json.dump(SCENARIOS_VAL, f, indent=2)
    if not os.path.exists("tests/benchmark_v2/scenarios_test_frozen.json"):
        with open("tests/benchmark_v2/scenarios_test_frozen.json", "w") as f:
            json.dump(SCENARIOS_TEST_FROZEN, f, indent=2)
    print("Benchmark V2 scenarios initialized.\n")

    summaries = []

    if args.split in ["dev", "all"]:
        dev = await run_scenario_suite("Development", SCENARIOS_DEV)
        summaries.append(dev)
    if args.split in ["val", "all"]:
        val = await run_scenario_suite("Validation", SCENARIOS_VAL)
        summaries.append(val)
    if args.split in ["frozen", "all"]:
        frozen = await run_scenario_suite("Frozen Test", SCENARIOS_TEST_FROZEN)
        summaries.append(frozen)

    print(f"\n{'='*75}")
    print(f"  BENCHMARK V2 FINAL REPORT")
    print(f"{'='*75}")
    print(f"  {'Split':<14} | {'Top-1':>6} | {'Budget':>7} | {'Hard':>6} | {'Stable':>7} | {'Regret':>7} | {'Latency':>8}")
    print(f"  {'-'*14}-+-{'-'*6}-+-{'-'*7}-+-{'-'*6}-+-{'-'*7}-+-{'-'*7}-+-{'-'*8}")
    for s in summaries:
        if s["executed"] > 0:
            print(f"  {s['suite']:<14} | {s['top1_agreement']:5.1f}% | {s['budget_compliance']:6.1f}% | {s['hard_compliance']:5.1f}% | {s['stability']:6.1f}% | {s['avg_regret']:7.4f} | {s['avg_latency_ms']:6.0f}ms")
        else:
            print(f"  {s['suite']:<14} | {'ERR':>6} | {'ERR':>7} | {'ERR':>6} | {'ERR':>7} | {'ERR':>7} | {'ERR':>8}")
    print(f"{'='*75}")

    # Write timestamped run record
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_file = f"tests/benchmark_v2/runs/run_{timestamp_str}.json"
    run_record = {
        "timestamp": datetime.now().isoformat(),
        "split_evaluated": args.split,
        "summaries": summaries
    }
    with open(run_file, "w") as f:
        json.dump(run_record, f, indent=2)
    print(f"\nSaved benchmark run record to {run_file}\n")


if __name__ == "__main__":
    asyncio.run(main())
