from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.base import Base, CRUDBase

class Message(Base, CRUDBase):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    content = Column(Text, nullable=True)  # Can be null if it's a file message
    
    # File attachment fields
    has_attachment = Column(Boolean, default=False)
    file_url = Column(String, nullable=True)
    file_type = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)  # Size in bytes
    
    # Reply and forward fields
    reply_to_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    forwarded_from_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    
    is_delivered = Column(Boolean, default=False)
    delivered_at = Column(DateTime, nullable=True)
    
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # For storing read receipts in group chats
    read_by = Column(JSON, default=list)
    
    @classmethod
    async def get_conversation(
        cls, 
        db: AsyncSession, 
        user1_id: int, 
        user2_id: int, 
        skip: int = 0, 
        limit: int = 50,
        date_from: datetime = None,
        date_to: datetime = None,
        has_attachment: bool = None
    ):
        """Get conversation between two users with filters."""
        query = select(cls).where(
            (
                ((cls.sender_id == user1_id) & (cls.receiver_id == user2_id)) |
                ((cls.sender_id == user2_id) & (cls.receiver_id == user1_id))
            ) &
            (cls.is_deleted == False) &
            (cls.group_id == None)  # Ensure it's a direct message
        )
        
        # Apply filters
        if date_from:
            query = query.where(cls.created_at >= date_from)
        if date_to:
            query = query.where(cls.created_at <= date_to)
        if has_attachment is not None:
            query = query.where(cls.has_attachment == has_attachment)
            
        query = query.order_by(cls.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @classmethod
    async def search_messages(
        cls,
        db: AsyncSession,
        user_id: int,
        search_term: str,
        skip: int = 0,
        limit: int = 50
    ):
        """Search for messages containing a specific term."""
        # This is a simple implementation - in production, you'd use full-text search
        query = select(cls).where(
            (
                ((cls.sender_id == user_id) | (cls.receiver_id == user_id)) &
                (cls.is_deleted == False) &
                (cls.content.ilike(f"%{search_term}%"))
            )
        )
        
        query = query.order_by(cls.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @classmethod
    async def mark_as_delivered(cls, db: AsyncSession, message_id: int):
        """Mark a message as delivered."""
        message = await cls.get_by_id(db, message_id)
        if message and not message.is_delivered:
            message.is_delivered = True
            message.delivered_at = datetime.utcnow()
            await db.commit()
            return True
        return False
    
    @classmethod
    async def mark_as_read(cls, db: AsyncSession, message_id: int, user_id: int = None):
        """Mark a message as read."""
        message = await cls.get_by_id(db, message_id)
        if not message:
            return False
            
        # For direct messages
        if message.receiver_id and message.receiver_id == user_id and not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
            await db.commit()
            return True
            
        # For group messages
        if message.group_id and user_id:
            read_by = message.read_by or []
            if user_id not in read_by:
                read_by.append(user_id)
                message.read_by = read_by
                await db.commit()
                return True
                
        return False
