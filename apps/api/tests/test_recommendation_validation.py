import asyncio
import os
import sys
from uuid import uuid4

# Add the apps/api directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from app.db.session import async_session_maker
from app.models.user import User
from app.models.decision import Decision
from app.models.question import Question
from app.models.answer import Answer
from app.services.recommendation_service import RecommendationService

VALIDATION_SCENARIOS = [
    {
        "name": "Gaming Laptop Rs 60k",
        "query": "Gaming Laptop under Rs 60000",
        "category": "laptop",
        "subtype": "gaming",
        "budget": 60000.0,
        "expected_subtype_db": "gaming"
    },
    {
        "name": "Gaming Laptop Rs 80k",
        "query": "Gaming Laptop under Rs 80000",
        "category": "laptop",
        "subtype": "gaming",
        "budget": 80000.0,
        "expected_subtype_db": "gaming"
    },
    {
        "name": "Gaming Laptop Rs 100k",
        "query": "Gaming Laptop under Rs 100000",
        "category": "laptop",
        "subtype": "gaming",
        "budget": 100000.0,
        "expected_subtype_db": "gaming"
    },
    {
        "name": "Gaming Laptop Rs 150k",
        "query": "Gaming Laptop under Rs 150000",
        "category": "laptop",
        "subtype": "gaming",
        "budget": 150000.0,
        "expected_subtype_db": "gaming"
    },
    {
        "name": "Business Laptop Rs 60k",
        "query": "Business Laptop under Rs 60000",
        "category": "laptop",
        "subtype": "business",
        "budget": 60000.0,
        "expected_subtype_db": "business"
    },
    {
        "name": "Programming Laptop Rs 90k",
        "query": "Programming Laptop under Rs 90000",
        "category": "laptop",
        "subtype": "programming",
        "budget": 90000.0,
        "expected_subtype_db": "developer"
    },
    {
        "name": "Phone Rs 25k",
        "query": "Phone under Rs 25000",
        "category": "smartphone",
        "subtype": "general",
        "budget": 25000.0,
        "expected_subtype_db": "general"
    },
    {
        "name": "Phone Rs 35k",
        "query": "Phone under Rs 35000",
        "category": "smartphone",
        "subtype": "general",
        "budget": 35000.0,
        "expected_subtype_db": "general"
    },
    {
        "name": "Monitor Rs 20k",
        "query": "Monitor under Rs 20000",
        "category": "monitor",
        "subtype": "general",
        "budget": 20000.0,
        "expected_subtype_db": "general"
    },
    {
        "name": "Monitor Rs 50k",
        "query": "Monitor under Rs 50000",
        "category": "monitor",
        "subtype": "general",
        "budget": 50000.0,
        "expected_subtype_db": "general"
    }
]

async def run_validation():
    print("==================================================")
    print("RUNNING PIPELINE STABILIZATION VALIDATION SUITE")
    print("==================================================")
    
    passed = 0
    failed = 0
    
    async with async_session_maker() as session:
        # Get or create a mock user
        result = await session.execute(select(User).limit(1))
        user = result.scalars().first()
        if not user:
            user = User(
                id=uuid4(),
                email="test-validation@nexus.ai",
                password_hash="test-hash"
            )
            session.add(user)
            await session.flush()
            await session.commit()
            
        for idx, scenario in enumerate(VALIDATION_SCENARIOS):
            print(f"\nScenario #{idx+1}: {scenario['name']} ('{scenario['query']}')")
            
            # Create the Decision
            decision = Decision(
                id=uuid4(),
                user_id=user.id,
                category=scenario["category"],
                subcategory=scenario["subtype"],
                title=scenario["query"],
                status="PENDING",
                currency="inr",
                detected_use_case="general",
                intent_confidence=95.0
            )
            session.add(decision)
            await session.flush()

            # Add budget question & answer
            q = Question(
                id=uuid4(),
                decision_id=decision.id,
                order_index=1,
                question_text="What is your maximum budget?",
                input_type="budget_range",
                options={"maps_to": "price"},
                weight_impact={"maps_to": "price"}
            )
            session.add(q)
            await session.flush()

            a = Answer(
                decision_id=decision.id,
                question_id=q.id,
                selected_value={"value": float(scenario["budget"])}
            )
            session.add(a)
            await session.flush()
            await session.commit()

            # Generate recommendation
            rec_service = RecommendationService(session)
            try:
                rec = await rec_service.generate_recommendation(decision.id)
                await session.commit()

                # Assertions
                assert rec is not None, "Recommendation is None"
                assert rec.structured_analysis is not None, "structured_analysis is None"
                
                # Check debug trace
                debug_trace = rec.structured_analysis.get("debug_trace")
                assert debug_trace is not None, "debug_trace is missing"
                assert debug_trace["loaded_products"] > 0, "loaded_products is 0"
                
                # Check pipeline trace
                trace = rec.structured_analysis.get("decision_trace")
                assert trace is not None, "decision_trace is missing"
                assert "pipeline_trace" in trace, "pipeline_trace is missing"
                
                if rec.verdict_product:
                    price = float(rec.verdict_product.price_inr)
                    print(f"  -> Winner: {rec.verdict_product.name}")
                    print(f"  -> Price: Rs {price:,.0f} (Budget: Rs {scenario['budget']:,.0f})")
                    
                    assert price <= scenario["budget"], f"Winner price Rs {price:,.0f} exceeds budget Rs {scenario['budget']:,.0f}"
                    assert rec.verdict_product.category == scenario["category"], f"Expected category {scenario['category']}, got {rec.verdict_product.category}"
                    
                    # Check database subtype
                    specs = rec.verdict_product.specs
                    subtype_key = "laptop_type" if scenario["category"] == "laptop" else ("phone_type" if scenario["category"] == "smartphone" else "monitor_type")
                    prod_sub = specs.get(subtype_key, "general")
                    
                    if scenario["expected_subtype_db"] != "general":
                        assert prod_sub == scenario["expected_subtype_db"], f"Expected product subtype {scenario['expected_subtype_db']}, got {prod_sub}"
                else:
                    print("  -> No Match Found")
                    # If no match, make sure it's valid (e.g. budget is too low)
                    assert scenario["budget"] < 50000.0 or scenario["category"] == "monitor" or scenario["category"] == "smartphone", "Unexpected No Match for high budget"
                
                print("  => STATUS: PASSED")
                passed += 1
                
            except AssertionError as ae:
                print(f"  => STATUS: FAILED ({str(ae)})")
                failed += 1
            except Exception as e:
                print(f"  => STATUS: ERROR ({str(e)})")
                failed += 1
            finally:
                # Clean up
                await session.execute(delete(Answer).where(Answer.decision_id == decision.id))
                await session.execute(delete(Question).where(Question.decision_id == decision.id))
                await session.execute(delete(Decision).where(Decision.id == decision.id))
                await session.commit()
                
    print("\n==================================================")
    print("VALIDATION SUITE SUMMARY")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print("==================================================")
    
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(run_validation())
