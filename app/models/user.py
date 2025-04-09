from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from enum import Enum as PyEnum

from app.db.base import Base, CRUDBase

class UserRole(str, PyEnum):
    USER = "user"
    ADMIN = "admin"

class User(Base, CRUDBase):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    status_message = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    timezone = Column(String, default="UTC")
    
    is_active = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    verification_token_expires = Column(DateTime, nullable=True)
    
    show_online_status = Column(Boolean, default=True)
    show_last_seen = Column(Boolean, default=True)
    
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    
    # Two-factor authentication fields
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String, nullable=True)
    
    @classmethod
    async def get_by_email(cls, db: AsyncSession, email: str) -> Optional["User"]:
        """Get a user by email."""
        result = await db.execute(select(cls).where(cls.email == email))
        return result.scalars().first()
    
    @classmethod
    async def get_by_username(cls, db: AsyncSession, username: str) -> Optional["User"]:
        """Get a user by username."""
        result = await db.execute(select(cls).where(cls.username == username))
        return result.scalars().first()
    
    @classmethod
    async def get_by_verification_token(cls, db: AsyncSession, token: str) -> Optional["User"]:
        """Get a user by verification token."""
        result = await db.execute(select(cls).where(cls.verification_token == token))
        return result.scalars().first()
    
    @classmethod
    async def update_last_seen(cls, db: AsyncSession, user_id: int) -> None:
        """Update the last seen timestamp for a user."""
        user = await cls.get_by_id(db, user_id)
        if user:
            user.last_seen_at = datetime.utcnow()
            await db.commit()
    
    @classmethod
    async def get_all_users(cls, db: AsyncSession, skip: int = 0, limit: int = 100):
        """Get all users with pagination (admin function)."""
        result = await db.execute(select(cls).offset(skip).limit(limit))
        return result.scalars().all()
