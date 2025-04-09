from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.group import GroupMemberRole

class GroupBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    
    class Config:
        from_attributes = True

class GroupCreate(GroupBase):
    description: Optional[str] = None
    avatar_url: Optional[str] = None

class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = None
    avatar_url: Optional[str] = None

class GroupResponse(GroupBase):
    id: int
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: datetime

class GroupMemberBase(BaseModel):
    class Config:
        from_attributes = True

class GroupMemberResponse(GroupMemberBase):
    id: int
    user_id: int
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: GroupMemberRole
    joined_at: datetime

class GroupInvite(BaseModel):
    user_id: int
