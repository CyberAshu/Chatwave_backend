from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

class MessageBase(BaseModel):
    content: Optional[str] = None
    
    class Config:
        from_attributes = True

class MessageCreate(MessageBase):
    receiver_id: Optional[int] = None
    group_id: Optional[int] = None
    reply_to_id: Optional[int] = None
    forwarded_from_id: Optional[int] = None

class MessageUpdate(BaseModel):
    content: str

class MessageResponse(MessageBase):
    id: int
    sender_id: int
    receiver_id: Optional[int] = None
    group_id: Optional[int] = None
    created_at: datetime
    
    # File attachment fields
    has_attachment: bool = False
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    
    # Reply and forward fields
    reply_to_id: Optional[int] = None
    forwarded_from_id: Optional[int] = None
    
    is_delivered: bool
    delivered_at: Optional[datetime] = None
    is_read: bool
    read_at: Optional[datetime] = None
    is_edited: bool
    edited_at: Optional[datetime] = None
    
    # For group messages
    read_by: Optional[List[int]] = None

class MessageInDB(MessageBase):
    id: int
    sender_id: int
    receiver_id: Optional[int] = None
    group_id: Optional[int] = None
    created_at: datetime
    
    # File attachment fields
    has_attachment: bool
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    
    # Reply and forward fields
    reply_to_id: Optional[int] = None
    forwarded_from_id: Optional[int] = None
    
    is_delivered: bool
    delivered_at: Optional[datetime] = None
    is_read: bool
    read_at: Optional[datetime] = None
    is_edited: bool
    edited_at: Optional[datetime] = None
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    
    # For group messages
    read_by: Optional[List[int]] = None
