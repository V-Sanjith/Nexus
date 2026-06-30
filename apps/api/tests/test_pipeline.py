import asyncio
import sys
import os
import logging
from uuid import uuid4

# Suppress SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Add the apps/api directory to python path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from app.db.session import async_session_maker, engine
from app.models.user import User
from app.models.product import Product
from app.models.decision import Decision
from app.models.question import Question
from app.models.answer import Answer
from app.services.recommendation_service import RecommendationService
from app.services.currency_service import CurrencyService

TEST_SCENARIOS = [
    {
        "query": "Gaming Laptop under Rs 40000",
        "category": "laptop",
        "currency": "inr",
        "expected_winner": None, # Expecting No Match
        "budget_limit": 40000
    },
    {
        "query": "Gaming Laptop under Rs 60000",
        "category": "laptop",
        "currency": "inr",
        "expected_winner": "HP Victus",
        "budget_limit": 60000
    },
    {
        "query": "Gaming Laptop under Rs 80000",
        "category": "laptop",
        "currency": "inr",
        "expected_winner": ["Lenovo LOQ", "Acer Nitro"],
        "budget_limit": 80000
    },
    {
        "query": "Gaming Laptop under Rs 100000",
        "category": "laptop",
        "currency": "inr",
        "expected_winner": ["Lenovo LOQ", "ASUS TUF"],
        "budget_limit": 100000
    },
    {
        "query": "Gaming Laptop under Rs 150000",
        "category": "laptop",
        "currency": "inr",
        "expected_winner": "ROG Zephyrus G14",
        "budget_limit": 150000
    },
    {
        "query": "Phone under Rs 25000",
        "category": "smartphone",
        "currency": "inr",
        "expected_winner": "Nothing Phone 2a",
        "budget_limit": 25000
    },
    {
        "query": "Phone under Rs 35000",
        "category": "smartphone",
        "currency": "inr",
        "expected_winner": ["OnePlus Nord", "Nothing Phone 2a", "Galaxy A55", "Realme GT 6T"],
        "budget_limit": 35000
    },
    {
        "query": "Business Laptop under Rs 60000",
        "category": "laptop",
        "currency": "inr",
        "expected_winner": ["ThinkPad E14", "ProBook"],
        "budget_limit": 60000
    },
    {
        "query": "Programming Laptop under Rs 90000",
        "category": "laptop",
        "currency": "inr",
        "expected_winner": "ThinkPad",
        "budget_limit": 90000
    }
]

async def run_tests():
    print("==================================================")
    print("RUNNING PIPELINE DETERMINISTIC TEST SUITE")
    print("==================================================")
    
    passed_tests = 0
    failed_tests = 0

    async with async_session_maker() as session:
        # Get or create a mock user
        result = await session.execute(select(User).limit(1))
        user = result.scalars().first()
        if not user:
            user = User(
                id=uuid4(),
                email="test-user@nexus.ai",
                password_hash="test-hash"
            )
            session.add(user)
            await session.flush()
            await session.commit()
            print(f"Created mock user: {user.email} ({user.id})")
        else:
            print(f"Using existing user: {user.email} ({user.id})")

        for idx, scenario in enumerate(TEST_SCENARIOS):
            print(f"\nTest Case #{idx+1}: '{scenario['query']}'")
            
            # 1. Create a mock Decision
            decision = Decision(
                id=uuid4(),
                user_id=user.id,
                category=scenario["category"],
                subcategory="general", # will be auto-detected by engine
                title=scenario["query"],
                status="PENDING",
                currency=scenario["currency"],
                detected_use_case="general",
                intent_confidence=95.0
            )
            session.add(decision)
            await session.flush()
            
            # 2. Add budget question & answer
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
                selected_value={"value": float(scenario["budget_limit"])}
            )
            session.add(a)
            await session.flush()
            await session.commit()
            
            # 3. Generate recommendation
            rec_service = RecommendationService(session)
            try:
                rec = await rec_service.generate_recommendation(decision.id)
                await session.commit()
                
                status = rec.structured_analysis.get("decision_trace", {}).get("status")
                verdict_product = rec.verdict_product
                
                # Assert budget is strictly respected
                if verdict_product:
                    price_inr = float(verdict_product.price_inr)
                    
                    print(f"  -> Match Found: {verdict_product.name}")
                    print(f"  -> Price: Rs {price_inr:,.0f} (Budget Limit: Rs {scenario['budget_limit']:,.0f})")
                    
                    assert price_inr <= scenario["budget_limit"], f"FAIL: Product price Rs {price_inr:,.0f} exceeds budget Rs {scenario['budget_limit']:,.0f}"
                    
                    # Assert expected winner
                    expected = scenario["expected_winner"]
                    if expected:
                        if isinstance(expected, list):
                            matched = any(exp.lower() in verdict_product.name.lower() for exp in expected)
                            assert matched, f"FAIL: Expected one of {expected}, got '{verdict_product.name}'"
                        else:
                            assert expected.lower() in verdict_product.name.lower(), f"FAIL: Expected '{expected}', got '{verdict_product.name}'"
                    else:
                        raise AssertionError(f"FAIL: Expected No Match, but got '{verdict_product.name}'")
                else:
                    print("  -> No Match Found (as expected or due to constraints)")
                    assert scenario["expected_winner"] is None, f"FAIL: Expected '{scenario['expected_winner']}', but got No Match"
                
                print("  => STATUS: PASSED")
                passed_tests += 1
                
            except AssertionError as ae:
                print(f"  => STATUS: FAILED ({str(ae)})")
                failed_tests += 1
            except Exception as e:
                print(f"  => STATUS: ERROR ({str(e)})")
                failed_tests += 1
                
            # Clean up the decision
            await session.execute(delete(Answer).where(Answer.decision_id == decision.id))
            await session.execute(delete(Question).where(Question.decision_id == decision.id))
            await session.execute(delete(Decision).where(Decision.id == decision.id))
            await session.commit()

    print("\n==================================================")
    print("TEST SUITE SUMMARY")
    print(f"  Passed: {passed_tests}")
    print(f"  Failed: {failed_tests}")
    print("==================================================")
    
    if failed_tests > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(run_tests())
