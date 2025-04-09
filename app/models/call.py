from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.base import Base, CRUDBase

class CallStatus(str, PyEnum):
    INITIATED = "initiated"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    MISSED = "missed"
    COMPLETED = "completed"

class Call(Base, CRUDBase):
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    caller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(CallStatus), default=CallStatus.INITIATED, nullable=False)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    answered_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    duration_seconds = Column(Integer, nullable=True)
    quality_score = Column(Integer, nullable=True)  # 1-5 rating
    
    @classmethod
    async def get_call_history(
        cls, 
        db: AsyncSession, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 20
    ):
        """Get call history for a user."""
        result = await db.execute(
            select(cls)
            .where(
                (cls.caller_id == user_id) | (cls.receiver_id == user_id)
            )
            .order_by(cls.started_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    @classmethod
    async def complete_call(cls, db: AsyncSession, call_id: int):
        """Mark a call as completed and calculate duration."""
        call = await cls.get_by_id(db, call_id)
        if call and call.status == CallStatus.ACCEPTED:
            call.status = CallStatus.COMPLETED
            call.ended_at = datetime.utcnow()
            
            if call.answered_at:
                # Calculate duration in seconds
                duration = (call.ended_at - call.answered_at).total_seconds()
                call.duration_seconds = int(duration)
            
            await db.commit()
            return True
        return False
