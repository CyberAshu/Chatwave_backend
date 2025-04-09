from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import relationship

from app.db.base import Base, CRUDBase

class GroupMemberRole(str, PyEnum):
    ADMIN = "admin"
    MEMBER = "member"

class Group(Base, CRUDBase):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    async def get_user_groups(cls, db: AsyncSession, user_id: int):
        """Get all groups a user is a member of."""
        # First get all group memberships for the user
        memberships_query = select(GroupMember.group_id).where(
            (GroupMember.user_id == user_id) & 
            (GroupMember.is_active == True)
        )
        memberships_result = await db.execute(memberships_query)
        group_ids = [row[0] for row in memberships_result]
        
        if not group_ids:
            return []
            
        # Then get the groups
        groups_query = select(cls).where(cls.id.in_(group_ids))
        groups_result = await db.execute(groups_query)
        return groups_result.scalars().all()

class GroupMember(Base, CRUDBase):
    __tablename__ = "group_members"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(GroupMemberRole), default=GroupMemberRole.MEMBER, nullable=False)
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    @classmethod
    async def get_group_members(cls, db: AsyncSession, group_id: int):
        """Get all active members of a group."""
        query = select(cls).where(
            (cls.group_id == group_id) & 
            (cls.is_active == True)
        )
        result = await db.execute(query)
        return result.scalars().all()
    
    @classmethod
    async def is_member(cls, db: AsyncSession, group_id: int, user_id: int):
        """Check if a user is an active member of a group."""
        query = select(cls).where(
            (cls.group_id == group_id) & 
            (cls.user_id == user_id) & 
            (cls.is_active == True)
        )
        result = await db.execute(query)
        return result.scalars().first() is not None
    
    @classmethod
    async def is_admin(cls, db: AsyncSession, group_id: int, user_id: int):
        """Check if a user is an admin of a group."""
        query = select(cls).where(
            (cls.group_id == group_id) & 
            (cls.user_id == user_id) & 
            (cls.is_active == True) &
            (cls.role == GroupMemberRole.ADMIN)
        )
        result = await db.execute(query)
        return result.scalars().first() is not None
