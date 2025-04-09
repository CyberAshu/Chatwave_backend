from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.base import Base, CRUDBase

class ActivityType(str, PyEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    SEND_MESSAGE = "send_message"
    EDIT_MESSAGE = "edit_message"
    DELETE_MESSAGE = "delete_message"
    CALL_INITIATED = "call_initiated"
    CALL_ACCEPTED = "call_accepted"
    CALL_DECLINED = "call_declined"
    CALL_ENDED = "call_ended"
    CREATE_GROUP = "create_group"
    JOIN_GROUP = "join_group"
    LEAVE_GROUP = "leave_group"
    SEND_FRIEND_REQUEST = "send_friend_request"
    ACCEPT_FRIEND_REQUEST = "accept_friend_request"
    REJECT_FRIEND_REQUEST = "reject_friend_request"
    UPLOAD_FILE = "upload_file"
    UPDATE_PROFILE = "update_profile"
    EMAIL_VERIFIED = "email_verified"

class ActivityLog(Base, CRUDBase):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activity_type = Column(Enum(ActivityType), nullable=False)
    description = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    @classmethod
    async def log_activity(
        cls, 
        db: AsyncSession, 
        user_id: int, 
        activity_type: ActivityType, 
        description: str = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """Log a user activity."""
        await cls.create(
            db,
            user_id=user_id,
            activity_type=activity_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @classmethod
    async def get_user_activity(
        cls, 
        db: AsyncSession, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 50,
        activity_type: ActivityType = None
    ):
        """Get activity logs for a user with optional filtering."""
        query = select(cls).where(cls.user_id == user_id)
        
        if activity_type:
            query = query.where(cls.activity_type == activity_type)
            
        query = query.order_by(cls.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
