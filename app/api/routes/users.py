from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information."""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_user_info(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user information."""
    updated_user = await User.update(
        db,
        current_user.id,
        **user_update.dict(exclude_unset=True)
    )
    return updated_user

@router.get("/{username}", response_model=UserResponse)
async def get_user_by_username(
    username: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user information by username."""
    user = await User.get_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Apply privacy settings
    response = UserResponse.from_orm(user)
    
    if user.show_online_status:
        response.online_status = True  # Simplified, in real app check WebSocket connections
    
    if user.show_last_seen:
        response.last_seen = user.last_seen_at
    
    return response

@router.get("/search/{query}", response_model=List[UserResponse])
async def search_users(
    query: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Search users by username or email."""
    # This is a simplified implementation
    # In a real app, you'd use a more sophisticated search
    if len(query) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 3 characters"
        )
    
    # For demo purposes, just return users with matching username
    # In production, implement proper search with pagination
    result = await db.execute(
        select(User).where(User.username.ilike(f"%{query}%")).limit(10)
    )
    users = result.scalars().all()
    
    return users
