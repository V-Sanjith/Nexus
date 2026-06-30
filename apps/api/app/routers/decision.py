from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List, Dict, Any, Optional

from app.dependencies import get_db, get_guest_user
from app.models.user import User
from app.models.decision import Decision
from app.models.question import Question
from app.models.answer import Answer
from app.schemas.decision import DecisionStartRequest, DecisionSchema
from app.schemas.answer import AnswerSubmitRequest
from app.services.recommendation_service import RecommendationService
from app.services.category_registry import CategoryRegistry
from app.ai.intent import IntentClassifier


router = APIRouter(prefix="/api/decisions", tags=["Decisions"])

@router.post("", response_model=DecisionSchema, status_code=status.HTTP_201_CREATED)
async def start_decision(
    payload: DecisionStartRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_guest_user)
):
    """Starts a decision session by running intent classification and seeding the questions template."""
    intent_classifier = IntentClassifier()
    classification = await intent_classifier.classify(payload.title)
    
    registry = CategoryRegistry()
    category = payload.category.lower() if payload.category else classification.category
    
    config = registry.get(category)
    if not config:
        # Fallback to first available category
        available = registry.list_categories()
        category = available[0]["key"] if available else "laptop"
        config = registry.get(category)
        
    if payload.category and payload.category.lower() != classification.category:
        # Override specified - resolve subcategory & default persona
        keyword_result = registry.match_keywords(payload.title)
        if keyword_result and keyword_result[0] == category:
            subcategory = keyword_result[1]
            persona = keyword_result[2]
            confidence = 95.0
            persona_weights = None
        else:
            subcategory = "general"
            persona = "general"
            confidence = 100.0
            persona_weights = None
    else:
        subcategory = classification.subcategory
        persona = classification.persona
        confidence = classification.confidence
        persona_weights = classification.persona_weights

    # Create the Decision record
    decision = Decision(
        user_id=user.id,
        category=category,
        subcategory=subcategory,
        title=payload.title,
        status="PENDING",
        currency=payload.currency.lower() if payload.currency else "inr",
        detected_use_case=persona,
        intent_confidence=confidence,
        persona_weights=persona_weights
    )
    db.add(decision)
    await db.flush()

    # Seed category questions dynamically from registry config
    questions_tpl = registry.get_questions(category, subcategory=decision.subcategory, currency=decision.currency)
    for q_tpl in questions_tpl:
        opts = dict(q_tpl["options"]) if q_tpl["options"] else {}
        opts["maps_to"] = q_tpl["maps_to"]
        q = Question(
            decision_id=decision.id,
            order_index=q_tpl["order_index"],
            question_text=q_tpl["question_text"],
            input_type=q_tpl["input_type"],
            options=opts,
            weight_impact={"maps_to": q_tpl["maps_to"]}
        )
        db.add(q)
            
    await db.commit()
    await db.refresh(decision, ["questions"])
    decision.questions.sort(key=lambda x: x.order_index)
    return decision


@router.post("/{decision_id}/answers", status_code=status.HTTP_200_OK)
async def save_answers(
    decision_id: UUID,
    payload: AnswerSubmitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_guest_user)
):
    """Submits and persists user answers for the given decision session."""
    # Fetch decision
    stmt = select(Decision).where(Decision.id == decision_id, Decision.user_id == user.id)
    result = await db.execute(stmt)
    decision = result.scalars().first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision session not found.")

    for ans_sub in payload.answers:
        # Check if answer exists
        stmt_ans = select(Answer).where(
            Answer.decision_id == decision_id,
            Answer.question_id == ans_sub.question_id
        )
        result_ans = await db.execute(stmt_ans)
        existing_ans = result_ans.scalars().first()
        
        if existing_ans:
            existing_ans.selected_value = ans_sub.selected_value
        else:
            new_ans = Answer(
                decision_id=decision_id,
                question_id=ans_sub.question_id,
                selected_value=ans_sub.selected_value
            )
            db.add(new_ans)

    decision.status = "QUESTIONING"
    await db.commit()
    return {"status": "success", "message": "Answers saved successfully."}

@router.post("/{decision_id}/recommend", status_code=status.HTTP_200_OK)
async def run_recommendation(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_guest_user)
):
    """Executes Decision Engine math, triggers Gemini, and yields structured recommendation."""
    # Fetch decision first to verify ownership and get category
    stmt = select(Decision).where(Decision.id == decision_id, Decision.user_id == user.id)
    result = await db.execute(stmt)
    decision = result.scalars().first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision session not found.")

    rec_service = RecommendationService(db)
    try:
        recommendation = await rec_service.generate_recommendation(decision_id)
        # Commit the transaction
        await db.commit()
        
        registry = CategoryRegistry()
        
        # Return structured analysis output payload directly
        return {
            "id": str(recommendation.id) if recommendation.id else None,
            "status": recommendation.structured_analysis.get("decision_trace", {}).get("status", "success"),
            "verdict_product": {
                "id": str(recommendation.verdict_product.id),
                "sku": recommendation.verdict_product.sku,
                "name": recommendation.verdict_product.name,
                "price": float(recommendation.structured_analysis.get("local_price", recommendation.verdict_product.price_inr)),
                "symbol": recommendation.structured_analysis.get("local_symbol", "$"),
                "currency": recommendation.structured_analysis.get("local_currency", "usd"),
                "specs": recommendation.verdict_product.specs
            } if recommendation.verdict_product else None,
            "score": float(recommendation.confidence_score),
            "confidence": float(recommendation.confidence_score),
            "pros": recommendation.structured_analysis.get("pros", []),
            "cons": recommendation.structured_analysis.get("cons", []),
            "tradeoffs": recommendation.structured_analysis.get("tradeoffs", []),
            "reasoning": recommendation.structured_analysis.get("reasoning", ""),
            "summary": recommendation.structured_analysis.get("summary", ""),
            "citations": recommendation.structured_analysis.get("citations", []),
            "decision_trace": recommendation.structured_analysis.get("decision_trace", {}),
            "display_specs": registry.get_display_specs(decision.category),
            "suggestions": recommendation.structured_analysis.get("suggestions", []),
            "closest_matches": recommendation.structured_analysis.get("closest_matches", [])
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        import structlog
        tb = traceback.format_exc()
        structlog.get_logger().error("Recommendation execution failed", error=str(e), traceback=tb)
        raise HTTPException(status_code=500, detail=f"Recommendation engine error: {str(e)}")

@router.get("/{decision_id}", status_code=status.HTTP_200_OK)
async def get_decision_state(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_guest_user)
):
    """Retrieves full decision session state, matching questions, answers and results."""
    # Retrieve pre-joined
    rec_service = RecommendationService(db)
    decision = await rec_service.decision_repo.get_with_answers(decision_id)
    if not decision or decision.user_id != user.id:
        raise HTTPException(status_code=404, detail="Decision session not found.")
        
    registry = CategoryRegistry()

    # Gather recommendation if completed
    recommendation_payload = None
    if decision.recommendation:
        rec = decision.recommendation
        recommendation_payload = {
            "id": str(rec.id) if rec.id else None,
            "status": rec.structured_analysis.get("decision_trace", {}).get("status", "success"),
            "verdict_product": {
                "id": str(rec.verdict_product.id),
                "sku": rec.verdict_product.sku,
                "name": rec.verdict_product.name,
                "price": float(rec.structured_analysis.get("local_price", rec.verdict_product.price_inr)),
                "symbol": rec.structured_analysis.get("local_symbol", "$"),
                "currency": rec.structured_analysis.get("local_currency", "usd"),
                "specs": rec.verdict_product.specs
            } if rec.verdict_product else None,
            "confidence": float(rec.confidence_score),
            "pros": rec.structured_analysis.get("pros", []),
            "cons": rec.structured_analysis.get("cons", []),
            "tradeoffs": rec.structured_analysis.get("tradeoffs", []),
            "reasoning": rec.structured_analysis.get("reasoning", ""),
            "summary": rec.structured_analysis.get("summary", ""),
            "citations": rec.structured_analysis.get("citations", []),
            "decision_trace": rec.structured_analysis.get("decision_trace", {}),
            "display_specs": registry.get_display_specs(decision.category),
            "suggestions": rec.structured_analysis.get("suggestions", []),
            "closest_matches": rec.structured_analysis.get("closest_matches", [])
        }
    elif decision.status == "COMPLETE":
        try:
            rec = await rec_service.generate_recommendation(decision.id)
            recommendation_payload = {
                "id": None,
                "status": rec.structured_analysis.get("decision_trace", {}).get("status", "success"),
                "verdict_product": None,
                "confidence": float(rec.confidence_score),
                "pros": rec.structured_analysis.get("pros", []),
                "cons": rec.structured_analysis.get("cons", []),
                "tradeoffs": rec.structured_analysis.get("tradeoffs", []),
                "reasoning": rec.structured_analysis.get("reasoning", ""),
                "summary": rec.structured_analysis.get("summary", ""),
                "citations": rec.structured_analysis.get("citations", []),
                "decision_trace": rec.structured_analysis.get("decision_trace", {}),
                "display_specs": registry.get_display_specs(decision.category),
                "suggestions": rec.structured_analysis.get("suggestions", []),
                "closest_matches": rec.structured_analysis.get("closest_matches", [])
            }
        except Exception as e:
            import structlog
            structlog.get_logger().error("Dynamic fallback recommendation generation failed on GET", error=str(e))


    return {
        "id": str(decision.id),
        "title": decision.title,
        "category": decision.category,
        "status": decision.status,
        "currency": decision.currency,
        "questions": [
            {
                "id": str(q.id),
                "order_index": q.order_index,
                "question_text": q.question_text,
                "input_type": q.input_type,
                "options": q.options
            } for q in sorted(decision.questions, key=lambda x: x.order_index)
        ],
        "answers": [
            {
                "question_id": str(a.question_id),
                "selected_value": a.selected_value
            } for a in decision.answers
        ],
        "recommendation": recommendation_payload
    }
