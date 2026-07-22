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
from app.schemas.decision import DecisionStartRequest, DecisionSchema, IntentDetectRequest, IntentDetectResponse
from app.schemas.answer import AnswerSubmitRequest
from app.schemas.recommendation import StatelessRecommendRequest
from app.services.recommendation_service import RecommendationService
from app.services.category_registry import CategoryRegistry
from app.ai.intent import IntentClassifier
from app.config import settings

def _strip_proprietary_trace(response_dict: dict) -> dict:
    """
    Strips full_audit_trace from production API responses.
    Only returns it when ENV is not production (dev/debug mode).
    """
    if settings.ENV == "production":
        dt = response_dict.get("decision_trace")
        if isinstance(dt, dict):
            dt.pop("full_audit_trace", None)
            # Also strip from nested structured_analysis if present
        # Strip from top-level
        if "full_audit_trace" in response_dict:
            del response_dict["full_audit_trace"]
    return response_dict

router = APIRouter(prefix="/api/decisions", tags=["Decisions"])

@router.post("/detect-intent", response_model=IntentDetectResponse)
async def detect_intent(payload: IntentDetectRequest):
    """Instantly detects category, subcategory, persona, and question count for a search query."""
    intent_classifier = IntentClassifier()
    classification = await intent_classifier.classify(payload.query)
    
    registry = CategoryRegistry()
    category = classification.category
    
    config = registry.get(category)
    if not config:
        available = registry.list_categories()
        category = available[0]["key"] if available else "laptop"
        
    subcategory = classification.subcategory
    persona = classification.persona
    confidence = classification.confidence
    
    questions_tpl = registry.get_questions(category, subcategory=subcategory, currency="inr")
    
    return IntentDetectResponse(
        category=category,
        subcategory=subcategory,
        persona=persona,
        confidence=confidence,
        questions_count=len(questions_tpl)
    )

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
            "closest_matches": recommendation.structured_analysis.get("closest_matches", []),
            "funnel_metrics": recommendation.structured_analysis.get("funnel_metrics"),
            "confidence_breakdown": recommendation.structured_analysis.get("confidence_breakdown"),
            "domain_scores": recommendation.structured_analysis.get("domain_scores"),
            "component_percentiles": recommendation.structured_analysis.get("component_percentiles"),
            "use_case_rank": recommendation.structured_analysis.get("use_case_rank"),
            "user_preferences": recommendation.structured_analysis.get("user_preferences"),
            "reliability_score": recommendation.structured_analysis.get("reliability_score"),
            "reliability_reasons": recommendation.structured_analysis.get("reliability_reasons"),
            "battle_comparison": recommendation.structured_analysis.get("battle_comparison"),
            "upgrade_analysis": recommendation.structured_analysis.get("upgrade_analysis"),
            "spend_less_analysis": recommendation.structured_analysis.get("spend_less_analysis"),
            "sensitivity_analysis": recommendation.structured_analysis.get("sensitivity_analysis"),
            "reliability_breakdown": recommendation.structured_analysis.get("reliability_breakdown")
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
            "closest_matches": rec.structured_analysis.get("closest_matches", []),
            "funnel_metrics": rec.structured_analysis.get("funnel_metrics"),
            "confidence_breakdown": rec.structured_analysis.get("confidence_breakdown"),
            "domain_scores": rec.structured_analysis.get("domain_scores"),
            "component_percentiles": rec.structured_analysis.get("component_percentiles"),
            "use_case_rank": rec.structured_analysis.get("use_case_rank"),
            "user_preferences": rec.structured_analysis.get("user_preferences"),
            "reliability_score": rec.structured_analysis.get("reliability_score"),
            "reliability_reasons": rec.structured_analysis.get("reliability_reasons"),
            "battle_comparison": rec.structured_analysis.get("battle_comparison"),
            "upgrade_analysis": rec.structured_analysis.get("upgrade_analysis")
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
                "closest_matches": rec.structured_analysis.get("closest_matches", []),
                "funnel_metrics": rec.structured_analysis.get("funnel_metrics"),
                "confidence_breakdown": rec.structured_analysis.get("confidence_breakdown"),
                "domain_scores": rec.structured_analysis.get("domain_scores"),
                "component_percentiles": rec.structured_analysis.get("component_percentiles"),
                "use_case_rank": rec.structured_analysis.get("use_case_rank"),
                "user_preferences": rec.structured_analysis.get("user_preferences"),
                "reliability_score": rec.structured_analysis.get("reliability_score"),
                "reliability_reasons": rec.structured_analysis.get("reliability_reasons"),
                "battle_comparison": rec.structured_analysis.get("battle_comparison"),
                "upgrade_analysis": rec.structured_analysis.get("upgrade_analysis")
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


@router.post("/recommend-stateless", status_code=status.HTTP_200_OK)
async def run_recommendation_stateless(
    payload: StatelessRecommendRequest,
    db: AsyncSession = Depends(get_db)
):
    """Executes Decision Engine math, triggers ExplanationBuilder, and yields structured recommendation without saving state."""
    rec_service = RecommendationService(db)
    try:
        recommendation = await rec_service.generate_recommendation_stateless(payload)
        
        # Flatten and format response to match the stateful recommendation structure perfectly
        registry = CategoryRegistry()
        sa = recommendation["structured_analysis"]
        vp = recommendation["verdict_product"]
        
        return {
            "id": None,
            "status": sa.get("decision_trace", {}).get("status", "success"),
            "verdict_product": {
                "id": vp["id"],
                "sku": vp["sku"],
                "name": vp["name"],
                "price": float(sa.get("local_price", vp["price_inr"])),
                "symbol": sa.get("local_symbol", "$"),
                "currency": sa.get("local_currency", "usd"),
                "specs": vp["specs"]
            } if vp else None,
            "score": float(recommendation["confidence_score"]),
            "confidence": float(recommendation["confidence_score"]),
            "pros": sa.get("pros", []),
            "cons": sa.get("cons", []),
            "tradeoffs": sa.get("tradeoffs", []),
            "reasoning": sa.get("reasoning", ""),
            "summary": sa.get("summary", ""),
            "citations": sa.get("citations", []),
            "decision_trace": sa.get("decision_trace", {}),
            "display_specs": registry.get_display_specs(payload.category),
            "suggestions": sa.get("suggestions", []),
            "closest_matches": sa.get("closest_matches", []),
            "funnel_metrics": sa.get("funnel_metrics"),
            "confidence_breakdown": sa.get("confidence_breakdown"),
            "domain_scores": sa.get("domain_scores"),
            "component_percentiles": sa.get("component_percentiles"),
            "use_case_rank": sa.get("use_case_rank"),
            "user_preferences": sa.get("user_preferences"),
            "reliability_score": sa.get("reliability_score"),
            "reliability_reasons": sa.get("reliability_reasons"),
            "battle_comparison": sa.get("battle_comparison"),
            "upgrade_analysis": sa.get("upgrade_analysis"),
            "spend_less_analysis": sa.get("spend_less_analysis"),
            "sensitivity_analysis": sa.get("sensitivity_analysis"),
            "reliability_breakdown": sa.get("reliability_breakdown"),
            "guardrail_results": sa.get("decision_trace", {}).get("guardrail_results"),
            "audit_status": sa.get("decision_trace", {}).get("audit_status"),
            "is_near_tie": sa.get("decision_trace", {}).get("guardrail_results", {}).get("is_near_tie", False),
            "deciding_factor": sa.get("decision_trace", {}).get("guardrail_results", {}).get("deciding_factor")
        }
        return _strip_proprietary_trace(response)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        import structlog
        structlog.get_logger().error("Stateless recommendation failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/intent", status_code=status.HTTP_200_OK)
async def get_intent_parsing(q: str):
    """Parses intent instantly for homepage search intelligence."""
    if not q or len(q.strip()) < 3:
        return {"category": None, "subcategory": None, "persona": None, "confidence": 0.0}
    
    from app.services.category_registry import CategoryRegistry
    registry = CategoryRegistry()
    
    # Keyword matcher first
    res = registry.match_keywords(q.lower().strip())
    if res:
        category, subcategory, persona = res
        return {
            "category": category,
            "subcategory": subcategory,
            "persona": persona,
            "confidence": 98.0
        }
    
    # Try calling the Gemini intent classifier if available
    try:
        from app.ai.intent import IntentClassifier
        classifier = IntentClassifier(registry)
        intent_res = await classifier.classify(q)
        return {
            "category": intent_res.category,
            "subcategory": intent_res.subcategory,
            "persona": intent_res.persona,
            "confidence": intent_res.confidence
        }
    except Exception:
        # Generic fallback
        return {
            "category": "laptop",
            "subcategory": "general",
            "persona": "general",
            "confidence": 40.0
        }


