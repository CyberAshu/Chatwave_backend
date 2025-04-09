from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.friendship import FriendshipStatus

class FriendshipBase(BaseModel):
    class Config:
        from_attributes = True

class FriendshipCreate(FriendshipBase):
    addressee_id: int

class FriendshipUpdate(FriendshipBase):
    status: FriendshipStatus

class FriendshipResponse(FriendshipBase):
    id: int
    requester_id: int
    addressee_id: int
    status: FriendshipStatus
    created_at: datetime
    updated_at: datetime

class FriendRequestResponse(BaseModel):
    id: int
    requester_id: int
    requester_username: str
    requester_avatar: Optional[str] = None
    created_at: datetime
