from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.activity_log import ActivityType

class ActivityLogBase(BaseModel):
    class Config:
        from_attributes = True

class ActivityLogResponse(ActivityLogBase):
    id: int
    user_id: int
    activity_type: ActivityType
    description: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
