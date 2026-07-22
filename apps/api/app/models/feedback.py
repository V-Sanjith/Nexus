from sqlalchemy import Column, String, Float, DateTime, Text, Enum as SQLEnum
import enum
from datetime import datetime
import uuid
from app.db.base import BaseModel

class FeedbackRating(str, enum.Enum):
    YES = "Yes"
    SOMEWHAT = "Somewhat"
    NO = "No"

class RejectionReason(str, enum.Enum):
    TOO_EXPENSIVE = "Too expensive"
    WRONG_PRIORITIES = "Wrong priorities"
    PREFER_ANOTHER = "I prefer another product"
    MISSING_OPTION = "Missing important option"
    MAKES_NO_SENSE = "Recommendation did not make sense"
    OTHER = "Other"

class UserFeedback(BaseModel):
    """
    Observational user feedback data store.
    Used exclusively for analytics and quality auditing. Never mutates MCDA weights.
    """
    __tablename__ = "user_feedback"

    decision_id = Column(String(36), nullable=True, index=True)
    rating = Column(String(20), nullable=False)
    rejection_reason = Column(String(50), nullable=True)
    comment = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    reliability_score = Column(Float, nullable=True)
