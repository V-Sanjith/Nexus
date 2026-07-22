import asyncio
import sys
import os
import json
import logging
from uuid import uuid4

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from app.db.session import async_session_maker
from app.models.user import User
from app.models.product import Product
from app.models.decision import Decision
from app.models.question import Question
from app.models.answer import Answer
from app.services.recommendation_service import RecommendationService
from app.services.category_registry import CategoryRegistry
from app.services.score_calculator import ScoreCalculator

async def debug_validation_suite():
    registry = CategoryRegistry()
    
    with open("tests/benchmark_v2/scenarios_val.json") as f:
        scenarios_val = json.load(f)
        
    with open("tests/benchmark_v2/scenarios_test_frozen.json") as f:
        scenarios_frozen = json.load(f)

    async with async_session_maker() as session:
        user = (await session.execute(select(User).limit(1))).scalars().first()
        if not user:
            user = User(id=uuid4(), email="debug@nexus.ai", password_hash="hash")
            session.add(user)
            await session.commit()

        rec_service = RecommendationService(session)

        print("\n=================================================================")
        print("  DETAILED VALIDATION SCENARIO AUDIT")
        print("=================================================================\n")

        for sc in scenarios_val:
            decision_id = uuid4()
            d = Decision(
                id=decision_id,
                user_id=user.id,
                title=sc["name"],
                category=sc["category"],
                subcategory=sc.get("subcategory", "general"),
                status="QUESTIONNAIRE",
                currency="INR",
                detected_use_case="photography" if sc["category"] == "smartphone" else "general"
            )
            session.add(d)
            await session.flush()

            q_defs = registry.get_questions(sc["category"], sc.get("subcategory"), "inr")
            for idx, q_def in enumerate(q_defs, 1):
                maps_to = getattr(q_def, "maps_to", None) if hasattr(q_def, "maps_to") else q_def.get("maps_to")
                q_id = uuid4()
                db_q = Question(
                    id=q_id,
                    decision_id=decision_id,
                    order_index=idx,
                    question_text=getattr(q_def, "question_text", f"Q{idx}"),
                    input_type=getattr(q_def, "input_type", "single_choice"),
                    weight_impact={"maps_to": maps_to} if maps_to else None
                )
                session.add(db_q)
                await session.flush()

                val = None
                if maps_to == "price":
                    val = {"value": sc["budget"]}
                elif maps_to in sc["answers"]:
                    val = {"value": sc["answers"][maps_to]}
                else:
                    val = {"value": 3.0}

                session.add(Answer(decision_id=decision_id, question_id=q_id, selected_value=val))

            await session.commit()

            rec = await rec_service.generate_recommendation(decision_id)
            vp = rec.verdict_product
            
            print(f"Scenario ID: {sc['id']}")
            print(f"Query/Name:  '{sc['name']}'")
            print(f"Category:    {sc['category']} (Subtype: {sc.get('subcategory')})")
            print(f"Budget:      ₹{sc['budget']:,.0f}")
            print(f"Expected:    {sc.get('expected_winner')}")
            print(f"Actual Winner: {vp.name if vp else 'None'} (Price: ₹{float(vp.price_inr):,.0f} if vp else N/A)")
            
            # Check expected winner in product catalog
            all_prods = (await session.execute(select(Product).where(Product.category == sc["category"]))).scalars().all()
            exp_names = sc.get("expected_winner", [])
            if isinstance(exp_names, str):
                exp_names = [exp_names]
            
            exp_prods = [p for p in all_prods if any(e.lower() in p.name.lower() for e in exp_names)]
            print(f"Catalog Products Matching Expected Names ({exp_names}): {len(exp_prods)}")
            for ep in exp_prods[:3]:
                print(f"   - {ep.name} (Price: ₹{float(ep.price_inr):,.0f}, RAM: {ep.specs.get('ram_gb')}, Camera: {ep.specs.get('camera_mp')})")

            # Cleanup
            await session.execute(delete(Answer).where(Answer.decision_id == decision_id))
            await session.execute(delete(Question).where(Question.decision_id == decision_id))
            await session.execute(delete(Decision).where(Decision.id == decision_id))
            await session.commit()

        print("\n=================================================================")
        print("  FROZEN TEST SCENARIO AUDIT")
        print("=================================================================\n")

        for sc in scenarios_frozen:
            decision_id = uuid4()
            d = Decision(
                id=decision_id,
                user_id=user.id,
                title=sc["name"],
                category=sc["category"],
                subcategory=sc.get("subcategory", "general"),
                status="QUESTIONNAIRE",
                currency="INR",
                detected_use_case="general"
            )
            session.add(d)
            await session.flush()

            q_defs = registry.get_questions(sc["category"], sc.get("subcategory"), "inr")
            for idx, q_def in enumerate(q_defs, 1):
                maps_to = getattr(q_def, "maps_to", None) if hasattr(q_def, "maps_to") else q_def.get("maps_to")
                q_id = uuid4()
                db_q = Question(
                    id=q_id,
                    decision_id=decision_id,
                    order_index=idx,
                    question_text=getattr(q_def, "question_text", f"Q{idx}"),
                    input_type=getattr(q_def, "input_type", "single_choice"),
                    weight_impact={"maps_to": maps_to} if maps_to else None
                )
                session.add(db_q)
                await session.flush()

                val = None
                if maps_to == "price":
                    val = {"value": sc["budget"]}
                elif maps_to in sc["answers"]:
                    val = {"value": sc["answers"][maps_to]}
                else:
                    val = {"value": 3.0}

                session.add(Answer(decision_id=decision_id, question_id=q_id, selected_value=val))

            await session.commit()

            rec = await rec_service.generate_recommendation(decision_id)
            vp = rec.verdict_product
            expected = sc.get("expected_winner")
            
            winner_match = False
            if expected is None:
                winner_match = vp is None
            elif expected == "ANY_MATCH":
                winner_match = vp is not None
            elif isinstance(expected, list):
                winner_match = vp is not None and any(e.lower() in vp.name.lower() for e in expected)
            else:
                winner_match = vp is not None and expected.lower() in vp.name.lower()

            print(f"[{'PASS' if winner_match else 'DISAGREEMENT'}] Scenario {sc['id']}: '{sc['name']}'")
            print(f"   Expected: {expected}")
            print(f"   Actual:   {vp.name if vp else 'None'}")
            print(f"   Match:    {winner_match}\n")

            # Cleanup
            await session.execute(delete(Answer).where(Answer.decision_id == decision_id))
            await session.execute(delete(Question).where(Question.decision_id == decision_id))
            await session.execute(delete(Decision).where(Decision.id == decision_id))
            await session.commit()

if __name__ == "__main__":
    asyncio.run(debug_validation_suite())
