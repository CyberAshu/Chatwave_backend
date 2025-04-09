from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import relationship

from app.db.base import Base, CRUDBase

class FriendshipStatus(str, PyEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED = "blocked"

class Friendship(Base, CRUDBase):
    __tablename__ = "friendships"
    
    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    addressee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(FriendshipStatus), default=FriendshipStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Ensure unique relationships between users
    __table_args__ = (
        UniqueConstraint('requester_id', 'addressee_id', name='unique_friendship'),
    )
    
    @classmethod
    async def get_friendship(cls, db: AsyncSession, user1_id: int, user2_id: int):
        """Get friendship between two users regardless of who initiated it."""
        result = await db.execute(
            select(cls).where(
                ((cls.requester_id == user1_id) & (cls.addressee_id == user2_id)) |
                ((cls.requester_id == user2_id) & (cls.addressee_id == user1_id))
            )
        )
        return result.scalars().first()
    
    @classmethod
    async def get_friends(cls, db: AsyncSession, user_id: int):
        """Get all accepted friends for a user."""
        result = await db.execute(
            select(cls).where(
                (
                    ((cls.requester_id == user_id) | (cls.addressee_id == user_id)) &
                    (cls.status == FriendshipStatus.ACCEPTED)
                )
            )
        )
        return result.scalars().all()
    
    @classmethod
    async def get_pending_requests(cls, db: AsyncSession, user_id: int):
        """Get all pending friend requests for a user."""
        result = await db.execute(
            select(cls).where(
                (cls.addressee_id == user_id) &
                (cls.status == FriendshipStatus.PENDING)
            )
        )
        return result.scalars().all()
