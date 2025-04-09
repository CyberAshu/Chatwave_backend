from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.call import CallStatus

class CallBase(BaseModel):
    class Config:
        from_attributes = True

class CallCreate(CallBase):
    receiver_id: int

class CallUpdate(CallBase):
    status: CallStatus
    quality_score: Optional[int] = None

class CallResponse(CallBase):
    id: int
    caller_id: int
    receiver_id: int
    status: CallStatus
    started_at: datetime
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    quality_score: Optional[int] = None
