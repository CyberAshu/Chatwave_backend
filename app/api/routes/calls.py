from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.models.call import Call, CallStatus
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User
from app.schemas.call import CallCreate, CallResponse, CallUpdate
from app.websockets.connection_manager import connection_manager

router = APIRouter()

@router.post("/", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
async def initiate_call(
    call: CallCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate a call to another user."""
    # Check if receiver exists
    receiver = await User.get_by_id(db, call.receiver_id)
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found"
        )
    
    # Check if users are friends
    friendship = await Friendship.get_friendship(db, current_user.id, call.receiver_id)
    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only call friends"
        )
    
    # Create call record
    new_call = await Call.create(
        db,
        caller_id=current_user.id,
        receiver_id=call.receiver_id,
        status=CallStatus.INITIATED
    )
    
    # Notify receiver if online
    if connection_manager.is_user_connected(call.receiver_id):
        await connection_manager.send_call_notification(
            call.receiver_id,
            {
                "type": "incoming_call",
                "call": {
                    "id": new_call.id,
                    "caller_id": current_user.id,
                    "caller_name": current_user.username,
                    "started_at": new_call.started_at.isoformat()
                }
            }
        )
    else:
        # If receiver is not online, mark as missed
        await Call.update(
            db,
            new_call.id,
            status=CallStatus.MISSED
        )
    
    return new_call

@router.put("/{call_id}", response_model=CallResponse)
async def update_call_status(
    call_id: int,
    call_update: CallUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update call status (accept, decline, complete)."""
    # Get call
    call = await Call.get_by_id(db, call_id)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Check if user is involved in the call
    if call.caller_id != current_user.id and call.receiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not involved in this call"
        )
    
    # Handle different status updates
    if call_update.status == CallStatus.ACCEPTED:
        if call.receiver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the receiver can accept a call"
            )
        
        if call.status != CallStatus.INITIATED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Call cannot be accepted in its current state"
            )
        
        # Update call as accepted
        updated_call = await Call.update(
            db,
            call_id,
            status=CallStatus.ACCEPTED,
            answered_at=datetime.utcnow()
        )
    
    elif call_update.status == CallStatus.DECLINED:
        if call.receiver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the receiver can decline a call"
            )
        
        if call.status != CallStatus.INITIATED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Call cannot be declined in its current state"
            )
        
        # Update call as declined
        updated_call = await Call.update(
            db,
            call_id,
            status=CallStatus.DECLINED
        )
    
    elif call_update.status == CallStatus.COMPLETED:
        # Either party can end the call
        if call.status != CallStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only active calls can be completed"
            )
        
        # Complete the call and calculate duration
        await Call.complete_call(db, call_id)
        updated_call = await Call.get_by_id(db, call_id)
        
        # Update quality score if provided
        if call_update.quality_score is not None:
            updated_call = await Call.update(
                db,
                call_id,
                quality_score=call_update.quality_score
            )
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid call status update"
        )
    
    # Notify the other party
    other_user_id = call.caller_id if current_user.id == call.receiver_id else call.receiver_id
    if connection_manager.is_user_connected(other_user_id):
        await connection_manager.send_call_notification(
            other_user_id,
            {
                "type": "call_status_updated",
                "call": {
                    "id": call.id,
                    "status": call_update.status
                }
            }
        )
    
    return updated_call

@router.get("/history", response_model=List[CallResponse])
async def get_call_history(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get call history for the current user."""
    calls = await Call.get_call_history(
        db,
        current_user.id,
        skip=skip,
        limit=limit
    )
    
    return calls
