import asyncio
import sys
import os
import time
import json
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import async_session_maker
from app.services.category_registry import CategoryRegistry
from app.services.decision_engine import DecisionEngine
from app.services.decision_guardrails import DecisionGuardrails
from app.services.decision_auditor import DecisionInvariantAuditor
from app.services.catalog_provider import LocalCatalogProvider
from app.ai.intent import IntentClassifier
from app.services.explanation_builder import ExplanationBuilder

async def measure_latency_breakdown():
    registry = CategoryRegistry()
    config = registry.get("laptop")
    engine = DecisionEngine(config)

    print("=" * 80)
    print("  LATENCY BREAKDOWN MEASUREMENT SUITE")
    print("=" * 80)

    # 1. Intent Detection Latency
    intent_latencies = []
    classifier = IntentClassifier()
    test_queries = [
        "Gaming laptop under Rs 1 lakh",
        "Best ultrabook for coding under Rs 120000",
        "Smartphone with great camera under 40000",
        "Productivity monitor for software development",
        "Gaming laptop with RTX 4060 under 90000"
    ]
    for q in test_queries:
        t0 = time.perf_counter()
        _ = await classifier.classify(q)
        dt = (time.perf_counter() - t0) * 1000.0
        intent_latencies.append(dt)

    # 2. Database Catalog Loading & Engine Execution Latency
    db_latencies = []
    engine_latencies = []
    guardrail_latencies = []
    
    answers = [
        {"maps_to": "price", "selected_value": {"value": 100000}},
        {"maps_to": "ram_gb", "selected_value": {"value": 16}},
        {"maps_to": "gpu_score", "selected_value": {"value": 4.0}}
    ]

    async with async_session_maker() as session:
        provider = LocalCatalogProvider(session)
        for _ in range(10):
            t0 = time.perf_counter()
            products = await provider.get_products("laptop")
            dt_db = (time.perf_counter() - t0) * 1000.0
            db_latencies.append(dt_db)

            t0 = time.perf_counter()
            scored, trace, status = engine.run(products, answers, "₹")
            dt_engine = (time.perf_counter() - t0) * 1000.0
            engine_latencies.append(dt_engine)

            t0 = time.perf_counter()
            valid_scored, g_log = DecisionGuardrails.evaluate(scored, answers, config, engine, trace, "₹")
            dt_g = (time.perf_counter() - t0) * 1000.0
            guardrail_latencies.append(dt_g)

    # 3. Explanation Generation Latency
    expl_latencies = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = ExplanationBuilder.build(
            winner=scored[0] if scored else None,
            alternatives=scored[1:3] if len(scored) > 1 else [],
            tradeoffs=[],
            trace=trace,
            category_config=config,
            currency_symbol="₹"
        )
        dt_expl = (time.perf_counter() - t0) * 1000.0
        expl_latencies.append(dt_expl)

    def stats(arr):
        return {
            "mean": round(float(np.mean(arr)), 1),
            "median": round(float(np.median(arr)), 1),
            "p95": round(float(np.percentile(arr, 95)), 1),
            "min": round(float(np.min(arr)), 1),
            "max": round(float(np.max(arr)), 1)
        }

    print("\n--- LATENCY METRICS BREAKDOWN ---")
    print(f"1. Intent Detection LLM:    {stats(intent_latencies)}")
    print(f"2. DB Catalog Retrieval:    {stats(db_latencies)}")
    print(f"3. Decision Engine Math:    {stats(engine_latencies)}")
    print(f"4. Guardrails & Auditor:    {stats(guardrail_latencies)}")
    print(f"5. Explanation Generation:  {stats(expl_latencies)}")

    total_mean = stats(intent_latencies)["mean"] + stats(db_latencies)["mean"] + stats(engine_latencies)["mean"] + stats(guardrail_latencies)["mean"] + stats(expl_latencies)["mean"]
    print(f"\nEstimated Mean E2E Recommendation Latency: {total_mean:.1f} ms")

if __name__ == "__main__":
    asyncio.run(measure_latency_breakdown())
