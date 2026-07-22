from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.models.feedback import UserFeedback
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/feedback", tags=["Feedback"])

class FeedbackSubmitRequest(BaseModel):
    decision_id: Optional[str] = None
    rating: str = Field(..., description="Yes | Somewhat | No")
    rejection_reason: Optional[str] = None
    comment: Optional[str] = None
    category: Optional[str] = None
    reliability_score: Optional[float] = None

@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/{decision_id}", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackSubmitRequest,
    decision_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Submits user feedback on a recommendation.
    Stored strictly for observational quality analysis. Never mutates MCDA weights.
    """
    target_decision_id = decision_id or payload.decision_id
    feedback_entry = UserFeedback(
        decision_id=target_decision_id,
        rating=payload.rating,
        rejection_reason=payload.rejection_reason,
        comment=payload.comment,
        category=payload.category,
        reliability_score=payload.reliability_score
    )
    db.add(feedback_entry)
    await db.commit()
    await db.refresh(feedback_entry)

    logger.info("User feedback recorded", decision_id=target_decision_id, rating=payload.rating)
    return {"status": "success", "feedback_id": str(feedback_entry.id)}

@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_feedback_metrics(db: AsyncSession = Depends(get_db)):
    """
    Returns aggregate observational feedback metrics.
    """
    total_stmt = select(func.count(UserFeedback.id))
    total_res = await db.execute(total_stmt)
    total_count = total_res.scalar() or 0

    if total_count == 0:
        return {
            "total_feedback": 0,
            "helpfulness_rate": 0.0,
            "rejection_reasons_breakdown": {},
            "rejection_by_category": {},
            "avg_reliability_accepted_vs_rejected": {
                "accepted": 0.0,
                "rejected": 0.0
            }
        }

    yes_stmt = select(func.count(UserFeedback.id)).where(UserFeedback.rating == "Yes")
    yes_res = await db.execute(yes_stmt)
    yes_count = yes_res.scalar() or 0

    helpfulness_rate = round((yes_count / total_count) * 100.0, 1)

    # Rejection reasons breakdown
    reason_stmt = select(UserFeedback.rejection_reason, func.count(UserFeedback.id)).where(UserFeedback.rejection_reason.isnot(None)).group_by(UserFeedback.rejection_reason)
    reason_res = await db.execute(reason_stmt)
    rejection_reasons = {r: cnt for r, cnt in reason_res.all()}

    # Rejection by category
    cat_stmt = select(UserFeedback.category, func.count(UserFeedback.id)).where(UserFeedback.rating == "No").group_by(UserFeedback.category)
    cat_res = await db.execute(cat_stmt)
    rejection_by_cat = {c or "unknown": cnt for c, cnt in cat_res.all()}

    # Avg reliability accepted vs rejected
    acc_rel_stmt = select(func.avg(UserFeedback.reliability_score)).where(UserFeedback.rating == "Yes")
    acc_rel_res = await db.execute(acc_rel_stmt)
    avg_acc_rel = acc_rel_res.scalar() or 0.0

    rej_rel_stmt = select(func.avg(UserFeedback.reliability_score)).where(UserFeedback.rating == "No")
    rej_rel_res = await db.execute(rej_rel_stmt)
    avg_rej_rel = rej_rel_res.scalar() or 0.0

    return {
        "total_feedback": total_count,
        "helpfulness_rate": helpfulness_rate,
        "rejection_reasons_breakdown": rejection_reasons,
        "rejection_by_category": rejection_by_cat,
        "avg_reliability_accepted_vs_rejected": {
            "accepted": round(float(avg_acc_rel), 1),
            "rejected": round(float(avg_rej_rel), 1)
        }
    }
