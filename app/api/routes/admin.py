from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.models.user import User, UserRole
from app.models.message import Message
from app.models.activity_log import ActivityLog, ActivityType
from app.schemas.user import UserResponse
from app.schemas.message import MessageResponse
from app.schemas.activity_log import ActivityLogResponse

router = APIRouter()

async def get_current_admin(
    current_user: User = Depends(get_current_user),
):
    """Check if the current user is an admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all users (admin only)."""
    users = await User.get_all_users(db, skip=skip, limit=limit)
    return users

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_details(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed user information (admin only)."""
    user = await User.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.put("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate a user account (admin only)."""
    user = await User.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent deactivating other admins
    if user.role == UserRole.ADMIN and user.id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate another admin"
        )
    
    await User.update(
        db,
        user_id,
        is_active=False
    )
    
    return {"detail": f"User {user.username} has been deactivated"}

@router.put("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Activate a user account (admin only)."""
    user = await User.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await User.update(
        db,
        user_id,
        is_active=True
    )
    
    return {"detail": f"User {user.username} has been activated"}

@router.get("/messages", response_model=List[MessageResponse])
async def get_all_messages(
    skip: int = 0,
    limit: int = 100,
    user_id: int = None,
    date_from: datetime = None,
    date_to: datetime = None,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get messages with filters (admin only)."""
    query = select(Message)
    
    # Apply filters
    if user_id:
        query = query.where(
            (Message.sender_id == user_id) | (Message.receiver_id == user_id)
        )
    
    if date_from:
        query = query.where(Message.created_at >= date_from)
    
    if date_to:
        query = query.where(Message.created_at <= date_to)
    
    query = query.order_by(Message.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    return messages

@router.delete("/messages/{message_id}")
async def delete_message_admin(
    message_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a message (admin only)."""
    message = await Message.get_by_id(db, message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Soft delete message
    await Message.update(
        db,
        message_id,
        is_deleted=True,
        deleted_at=datetime.utcnow()
    )
    
    # Log admin action
    await ActivityLog.log_activity(
        db,
        current_admin.id,
        ActivityType.DELETE_MESSAGE,
        description=f"Admin deleted message {message_id} from user {message.sender_id}"
    )
    
    return {"detail": "Message has been deleted"}

@router.get("/activity-logs", response_model=List[ActivityLogResponse])
async def get_activity_logs(
    skip: int = 0,
    limit: int = 100,
    user_id: int = None,
    activity_type: ActivityType = None,
    date_from: datetime = None,
    date_to: datetime = None,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get activity logs with filters (admin only)."""
    query = select(ActivityLog)
    
    # Apply filters
    if user_id:
        query = query.where(ActivityLog.user_id == user_id)
    
    if activity_type:
        query = query.where(ActivityLog.activity_type == activity_type)
    
    if date_from:
        query = query.where(ActivityLog.created_at >= date_from)
    
    if date_to:
        query = query.where(ActivityLog.created_at <= date_to)
    
    query = query.order_by(ActivityLog.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return logs
