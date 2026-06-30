import asyncio
import time
import sys
import os
from uuid import uuid4, UUID
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()

# Adjust sys.path to run inside apps/api context
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.base import Base
from app.models.product import Product
from app.models.user import User
from app.models.decision import Decision
from app.models.question import Question
from app.models.answer import Answer
from app.services.recommendation_service import RecommendationService
from app.services.currency_service import CurrencyService

# Setup temporary test database engine (SQLite in-memory)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Seed dataset of 8 laptops
TEST_LAPTOPS = [
    {
        "sku": "apple-mba-m3-16-512",
        "name": "Apple MacBook Air 13 M3",
        "price_inr": 107702.00,
        "specs": {"ram_gb": 16, "storage_gb": 512, "weight_kg": 1.24, "battery_hours": 18.0, "cpu_score": 12000, "gpu_score": 3000, "screen_size": 13.6, "brand": "Apple", "laptop_type": "ultrabook", "historical_rating": 4.8}
    },
    {
        "sku": "asus-g14-2024-16-1tb",
        "name": "Asus ROG Zephyrus G14",
        "price_inr": 156702.00,
        "specs": {"ram_gb": 16, "storage_gb": 1024, "weight_kg": 1.50, "battery_hours": 8.0, "cpu_score": 18000, "gpu_score": 12000, "screen_size": 14.0, "brand": "Asus", "laptop_type": "gaming", "gpu_type": "dedicated", "historical_rating": 4.6}
    },
    {
        "sku": "lenovo-x1-carbon-32-1tb",
        "name": "Lenovo ThinkPad X1 Carbon Gen 12",
        "price_inr": 186102.00,
        "specs": {"ram_gb": 32, "storage_gb": 1024, "weight_kg": 1.09, "battery_hours": 12.0, "cpu_score": 14000, "gpu_score": 2500, "screen_size": 14.0, "brand": "Lenovo", "laptop_type": "developer", "historical_rating": 4.7}
    },
    {
        "sku": "acer-aspire-5-8-512",
        "name": "Acer Aspire 5",
        "price_inr": 48902.00,
        "specs": {"ram_gb": 8, "storage_gb": 512, "weight_kg": 1.78, "battery_hours": 7.0, "cpu_score": 8000, "gpu_score": 1000, "screen_size": 15.6, "brand": "Acer", "laptop_type": "budget", "historical_rating": 4.1}
    },
    {
        "sku": "dell-xps-16-32-1tb",
        "name": "Dell XPS 16",
        "price_inr": 244902.00,
        "specs": {"ram_gb": 32, "storage_gb": 1024, "weight_kg": 2.20, "battery_hours": 10.0, "cpu_score": 20000, "gpu_score": 9000, "screen_size": 16.3, "brand": "Dell", "laptop_type": "creator", "historical_rating": 4.4}
    },
    {
        "sku": "hp-pavilion-14-16-512",
        "name": "HP Pavilion Plus 14",
        "price_inr": 73402.00,
        "specs": {"ram_gb": 16, "storage_gb": 512, "weight_kg": 1.38, "battery_hours": 9.0, "cpu_score": 11000, "gpu_score": 1800, "screen_size": 14.0, "brand": "HP", "laptop_type": "student", "historical_rating": 4.3}
    },
    {
        "sku": "apple-mbp-16-48-1tb",
        "name": "Apple MacBook Pro 16 M3 Max",
        "price_inr": 342902.00,
        "specs": {"ram_gb": 48, "storage_gb": 1024, "weight_kg": 2.16, "battery_hours": 22.0, "cpu_score": 28000, "gpu_score": 18000, "screen_size": 16.2, "brand": "Apple", "laptop_type": "premium", "historical_rating": 4.9}
    },
    {
        "sku": "lenovo-yoga-9i-16-1tb",
        "name": "Lenovo Yoga 9i Convertible",
        "price_inr": 137102.00,
        "specs": {"ram_gb": 16, "storage_gb": 1024, "weight_kg": 1.35, "battery_hours": 11.0, "cpu_score": 13000, "gpu_score": 2200, "screen_size": 14.0, "brand": "Lenovo", "laptop_type": "convertible", "historical_rating": 4.5}
    }
]

# Benchmark Scenarios definitions
SCENARIOS = [
    # --- SUCCESS CASES ---
    {
        "id": 1,
        "name": "Student under INR 60,000 budget",
        "currency": "inr",
        "persona_hint": "Student",
        "answers": {
            "budget": 58800.0,  # ₹58,800 ($600 USD)
            "ram": 8,
            "storage": 256,
            "portability": 3,
            "battery": 3,
            "cpu": 2,
            "gpu": 1
        },
        "expected_status": "success",
        "target_sku": "acer-aspire-5-8-512"
    },
    {
        "id": 2,
        "name": "Gaming laptop under INR 1,60,000 budget",
        "currency": "inr",
        "persona_hint": "Gamer",
        "answers": {
            "budget": 160000.0,  # ₹160,000 ($1632 USD, enough to fit $1599)
            "ram": 16,
            "storage": 512,
            "portability": 2,
            "battery": 2,
            "cpu": 4,
            "gpu": 5
        },
        "expected_status": "success",
        "target_sku": "asus-g14-2024-16-1tb"
    },
    {
        "id": 3,
        "name": "Software Engineer (Developer)",
        "currency": "inr",
        "persona_hint": "Developer",
        "answers": {
            "budget": 196000.0,  # $2000 USD
            "ram": 32,
            "storage": 1024,
            "portability": 3,
            "battery": 4,
            "cpu": 5,
            "gpu": 2
        },
        "expected_status": "success",
        "target_sku": "lenovo-x1-carbon-32-1tb"
    },
    {
        "id": 4,
        "name": "MBA Student (Portability focus)",
        "currency": "inr",
        "persona_hint": "Student",
        "answers": {
            "budget": 117600.0,  # $1200 USD
            "ram": 16,
            "storage": 512,
            "portability": 5,
            "battery": 5,
            "cpu": 3,
            "gpu": 1
        },
        "expected_status": "success",
        "target_sku": "apple-mba-m3-16-512"
    },
    {
        "id": 5,
        "name": "Video Editor (Heavy Creator)",
        "currency": "inr",
        "persona_hint": "Video Editor",
        "answers": {
            "budget": 274400.0,  # $2800 USD
            "ram": 32,
            "storage": 1024,
            "portability": 2,
            "battery": 3,
            "cpu": 5,
            "gpu": 5
        },
        "expected_status": "success",
        "target_sku": "dell-xps-16-32-1tb"
    },
    {
        "id": 6,
        "name": "Frequent Traveller",
        "currency": "inr",
        "persona_hint": "Traveller",
        "answers": {
            "budget": 196000.0,  # $2000 USD
            "ram": 16,
            "storage": 512,
            "portability": 5,
            "battery": 5,
            "cpu": 3,
            "gpu": 2
        },
        "expected_status": "success",
        "target_sku": ["apple-mba-m3-16-512", "lenovo-x1-carbon-32-1tb"]
    },

    # --- FAILURE & BOUNDARY CASES ---
    {
        "id": 7,
        "name": "Impossible constraints (High RAM, Low budget)",
        "currency": "inr",
        "persona_hint": None,
        "answers": {
            "budget": 58800.0,  # $600 USD
            "ram": 32,  # 32GB RAM laptops cost at least $1890
            "storage": 512,
            "portability": 3,
            "battery": 3,
            "cpu": 3,
            "gpu": 3
        },
        "expected_status": "no_match_found",  # No 32GB RAM laptop exists under 58800 INR
        "target_sku": None
    },
    {
        "id": 8,
        "name": "Conflicting requirements (Max gaming + Max portability)",
        "currency": "inr",
        "persona_hint": None,
        "answers": {
            "budget": 196000.0,  # $2000 USD
            "ram": 16,
            "storage": 512,
            "portability": 5, # Slider 5 (Weight must be low)
            "battery": 2,
            "cpu": 4,
            "gpu": 5  # Slider 5 (Max gaming GPU requires heavy cooling)
        },
        "expected_status": "success",
        "target_sku": "asus-g14-2024-16-1tb" # G14 represents the best tradeoff (1.50kg)
    },
    {
        "id": 9,
        "name": "Extremely low budget (No catalog matches)",
        "currency": "inr",
        "persona_hint": None,
        "answers": {
            "budget": 19600.0,  # $200 USD. Cheapest is Acer Aspire 5 at $499
            "ram": 8,
            "storage": 256,
            "portability": 2,
            "battery": 2,
            "cpu": 2,
            "gpu": 1
        },
        "expected_status": "no_match_found",  # Triggers suggestion fallback
        "target_sku": None
    }
]

async def setup_test_db():
    """Initializes in-memory tables and seeds laptop catalog."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        # Seed Laptops
        for l_data in TEST_LAPTOPS:
            p = Product(
                sku=l_data["sku"],
                name=l_data["name"],
                category="laptop",
                price_inr=l_data["price_inr"],
                specs=l_data["specs"],
                is_active=True
            )
            session.add(p)
            
        # Seed guest user
        u = User(
            id=uuid4(),
            email="guest-test-runner@nexus.ai",
            password_hash="test_session_hash",
            is_deleted=False
        )
        session.add(u)
        await session.commit()
        return u.id

async def run_scenario(session: AsyncSession, guest_user_id: UUID, sc: Dict[str, Any]) -> Dict[str, Any]:
    """Runs a single benchmark scenario and returns metrics."""
    t_start = time.perf_counter()

    # 1. Create Decision record
    decision = Decision(
        user_id=guest_user_id,
        category="laptop",
        title=sc["name"],
        status="PENDING",
        currency=sc["currency"]
    )
    session.add(decision)
    await session.flush()

    # 2. Add Questions
    q_budget = Question(decision_id=decision.id, order_index=1, question_text="What is your maximum budget?", input_type="budget_range", weight_impact={"maps_to": "price"})
    q_ram = Question(decision_id=decision.id, order_index=2, question_text="What is your minimum memory (RAM) requirement?", input_type="single_choice", weight_impact={"maps_to": "ram_gb"})
    q_storage = Question(decision_id=decision.id, order_index=3, question_text="What is your minimum storage space requirement?", input_type="single_choice", weight_impact={"maps_to": "storage_gb"})
    q_portability = Question(decision_id=decision.id, order_index=4, question_text="How important is Portability (weight)?", input_type="slider", weight_impact={"maps_to": "weight_kg"})
    q_battery = Question(decision_id=decision.id, order_index=5, question_text="How important is Battery Life (runtime)?", input_type="slider", weight_impact={"maps_to": "battery_hours"})
    q_cpu = Question(decision_id=decision.id, order_index=6, question_text="How important is CPU/Processing performance?", input_type="slider", weight_impact={"maps_to": "cpu_score"})
    q_gpu = Question(decision_id=decision.id, order_index=7, question_text="How important is GPU/Gaming/Graphics performance?", input_type="slider", weight_impact={"maps_to": "gpu_score"})
    
    session.add_all([q_budget, q_ram, q_storage, q_portability, q_battery, q_cpu, q_gpu])
    await session.flush()

    # 3. Add Answers
    ans_map = {
        q_budget.id: sc["answers"]["budget"],
        q_ram.id: sc["answers"]["ram"],
        q_storage.id: sc["answers"]["storage"],
        q_portability.id: sc["answers"]["portability"],
        q_battery.id: sc["answers"]["battery"],
        q_cpu.id: sc["answers"]["cpu"],
        q_gpu.id: sc["answers"]["gpu"]
    }

    for q_id, val in ans_map.items():
        ans = Answer(decision_id=decision.id, question_id=q_id, selected_value={"value": val})
        session.add(ans)
    await session.flush()

    # 4. Invoke Recommendation Service
    rec_service = RecommendationService(session)

    # Execute
    recommendation = await rec_service.generate_recommendation(decision.id)
    await session.commit()
    
    t_end = time.perf_counter()
    runtime_ms = (t_end - t_start) * 1000

    # 5. Extract metrics from results
    winner_sku = recommendation.verdict_product.sku if recommendation.verdict_product else None
    trace = recommendation.structured_analysis["decision_trace"]
    status = trace["status"]
    confidence = recommendation.confidence_score

    # Check precision correctness
    if isinstance(sc["target_sku"], list):
        sku_match = winner_sku in sc["target_sku"]
    else:
        sku_match = (winner_sku == sc["target_sku"])
    precision_passed = sku_match and (status == sc["expected_status"])
    
    # Measure diversity: distance between winner and alternatives
    tradeoffs = recommendation.structured_analysis.get("tradeoffs", [])
    diversity_score = 0.0
    if tradeoffs:
        diversity_score = len(tradeoffs) / 2.0  # Simple alternative count diversity indicator

    return {
        "scenario_name": sc["name"],
        "expected_status": sc["expected_status"],
        "actual_status": status,
        "expected_sku": sc["target_sku"],
        "actual_sku": winner_sku,
        "precision_passed": precision_passed,
        "confidence": confidence,
        "runtime_ms": runtime_ms,
        "diversity_score": diversity_score,
        "relaxed_steps": len(trace.get("relaxation_log", []))
    }

async def run_all_benchmarks():
    logger.info("Initializing automated decision intelligence test suite...")
    guest_user_id = await setup_test_db()

    results = []
    
    async with async_session_maker() as session:
        for sc in SCENARIOS:
            logger.info("Executing benchmark scenario", name=sc["name"])
            res = await run_scenario(session, guest_user_id, sc)
            results.append(res)

    # Compile report markdown output
    passed_count = sum(1 for r in results if r["precision_passed"])
    total_scenarios = len(results)
    avg_precision = (passed_count / total_scenarios) * 100
    avg_runtime = sum(r["runtime_ms"] for r in results) / total_scenarios
    avg_confidence = sum(r["confidence"] for r in results) / total_scenarios

    report = []
    report.append("# Nexus Decision Intelligence Upgrade: Benchmark Scenarios Report")
    report.append(f"\n* **Total Scenarios Evaluated**: {total_scenarios}")
    report.append(f"* **Average Precision**: {avg_precision:.1f}% ({passed_count}/{total_scenarios} passed)")
    report.append(f"* **Average Evaluation Runtime**: {avg_runtime:.2f} ms")
    report.append(f"* **Average Recommendation Confidence**: {avg_confidence:.1f}%")
    report.append("\n## Scenario Results Breakdown\n")
    report.append("| ID | Scenario Name | Target SKU | Result SKU | Target Status | Result Status | Precision | Confidence | Runtime (ms) |")
    report.append("|---|---|---|---|---|---|---|---|---|")
    
    for idx, r in enumerate(results):
        pass_symbol = "✅ PASS" if r["precision_passed"] else "❌ FAIL"
        report.append(
            f"| {idx+1} | {r['scenario_name']} | `{r['expected_sku']}` | `{r['actual_sku']}` | `{r['expected_status']}` | `{r['actual_status']}` | {pass_symbol} | {r['confidence']:.1f}% | {r['runtime_ms']:.1f} |"
        )

    report_content = "\n".join(report)
    print("\n" + report_content + "\n")
    
    # Save report to a file in the workspace
    report_path = r"d:\Nexus\docs\architecture\decision-intelligence-report.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    logger.info("Decision intelligence report generated", path=report_path)

    # Exit with code 0 if all tests passed, else 1
    if passed_count == total_scenarios:
        logger.info("All decision engine intelligence checks passed successfully.")
        sys.exit(0)
    else:
        logger.error("Some decision engine intelligence checks failed.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())
