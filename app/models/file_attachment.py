from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.base import Base, CRUDBase

class FileAttachment(Base, CRUDBase):
    __tablename__ = "file_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    created_at = Column(DateTime, default=datetime.utcnow)
    
    @classmethod
    async def get_user_files(
        cls, 
        db: AsyncSession, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 50,
        file_type: str = None
    ):
        """Get files uploaded by a user with optional filtering."""
        query = select(cls).where(cls.user_id == user_id)
        
        if file_type:
            query = query.where(cls.file_type == file_type)
            
        query = query.order_by(cls.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
