from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User
from app.schemas.friendship import (
    FriendRequestResponse,
    FriendshipCreate,
    FriendshipResponse,
    FriendshipUpdate
)
from app.schemas.user import UserResponse

router = APIRouter()

@router.post("/request", response_model=FriendshipResponse, status_code=status.HTTP_201_CREATED)
async def send_friend_request(
    request: FriendshipCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a friend request to another user."""
    # Check if user exists
    addressee = await User.get_by_id(db, request.addressee_id)
    if not addressee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if trying to add self
    if current_user.id == request.addressee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send friend request to yourself"
        )
    
    # Check if friendship already exists
    existing = await Friendship.get_friendship(db, current_user.id, request.addressee_id)
    if existing:
        if existing.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already friends with this user"
            )
        elif existing.status == FriendshipStatus.PENDING:
            if existing.requester_id == current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Friend request already sent"
                )
            else:
                # The other user already sent a request, accept it
                existing.status = FriendshipStatus.ACCEPTED
                await db.commit()
                return existing
        elif existing.status == FriendshipStatus.BLOCKED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot send friend request to this user"
            )
    
    # Create new friendship
    friendship = await Friendship.create(
        db,
        requester_id=current_user.id,
        addressee_id=request.addressee_id,
        status=FriendshipStatus.PENDING
    )
    
    return friendship

@router.get("/requests", response_model=List[FriendRequestResponse])
async def get_friend_requests(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all pending friend requests for the current user."""
    requests = await Friendship.get_pending_requests(db, current_user.id)
    
    # Enrich with requester information
    result = []
    for req in requests:
        requester = await User.get_by_id(db, req.requester_id)
        if requester:
            result.append(
                FriendRequestResponse(
                    id=req.id,
                    requester_id=requester.id,
                    requester_username=requester.username,
                    requester_avatar=requester.avatar_url,
                    created_at=req.created_at
                )
            )
    
    return result

@router.put("/requests/{request_id}", response_model=FriendshipResponse)
async def respond_to_friend_request(
    request_id: int,
    response: FriendshipUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Respond to a friend request (accept, reject, block)."""
    # Get the request
    request = await Friendship.get_by_id(db, request_id)
    if not request or request.addressee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend request not found"
        )
    
    if request.status != FriendshipStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request is not pending"
        )
    
    # Update the request
    updated = await Friendship.update(
        db,
        request_id,
        status=response.status
    )
    
    return updated

@router.get("/", response_model=List[UserResponse])
async def get_friends(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all friends for the current user."""
    friendships = await Friendship.get_friends(db, current_user.id)
    
    # Get the friend user objects
    friends = []
    for friendship in friendships:
        friend_id = friendship.addressee_id if friendship.requester_id == current_user.id else friendship.requester_id
        friend = await User.get_by_id(db, friend_id)
        if friend:
            friends.append(friend)
    
    return friends

@router.delete("/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(
    friend_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a friend."""
    friendship = await Friendship.get_friendship(db, current_user.id, friend_id)
    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend not found"
        )
    
    await Friendship.delete(db, friendship.id)
    return None
