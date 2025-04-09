from typing import List
from datetime import datetime
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

from app.core.dependencies import get_current_active_user, get_db
from app.core.config import settings
from app.models.friendship import Friendship, FriendshipStatus
from app.models.message import Message
from app.models.file_attachment import FileAttachment
from app.models.user import User
from app.models.activity_log import ActivityLog, ActivityType
from app.schemas.message import MessageCreate, MessageResponse, MessageUpdate
from app.websockets.connection_manager import connection_manager

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.MESSAGE_RATE_LIMIT)
async def send_message(
    request: Request,
    message: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message to another user."""
    # Check if user is verified
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    
    # Check if receiver exists
    receiver = await User.get_by_id(db, message.receiver_id)
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found"
        )
    
    # Check if users are friends
    friendship = await Friendship.get_friendship(db, current_user.id, message.receiver_id)
    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send messages to friends"
        )
    
    # Create message
    new_message = await Message.create(
        db,
        sender_id=current_user.id,
        receiver_id=message.receiver_id,
        content=message.content,
        reply_to_id=message.reply_to_id,
        forwarded_from_id=message.forwarded_from_id
    )
    
    # Notify receiver if online
    if connection_manager.is_user_connected(message.receiver_id):
        await connection_manager.send_message_notification(
            message.receiver_id,
            {
                "type": "new_message",
                "message": {
                    "id": new_message.id,
                    "sender_id": current_user.id,
                    "content": message.content,
                    "created_at": new_message.created_at.isoformat(),
                    "reply_to_id": message.reply_to_id,
                    "forwarded_from_id": message.forwarded_from_id
                }
            }
        )
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        current_user.id,
        ActivityType.SEND_MESSAGE,
        description=f"Sent message to user {receiver.username}"
    )
    
    return new_message

@router.post("/upload-file", response_model=MessageResponse)
async def upload_file(
    receiver_id: int = Form(...),
    file: UploadFile = File(...),
    reply_to_id: int = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a file and send it as a message."""
    # Check if user is verified
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    
    # Check if receiver exists
    receiver = await User.get_by_id(db, receiver_id)
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found"
        )
    
    # Check if users are friends
    friendship = await Friendship.get_friendship(db, current_user.id, receiver_id)
    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send files to friends"
        )
    
    # Validate file size
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB chunks
    for chunk in iter(lambda: file.file.read(chunk_size), b""):
        file_size += len(chunk)
        if file_size > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE / (1024 * 1024)}MB"
            )
    
    # Reset file pointer
    await file.seek(0)
    
    # Validate file type
    content_type = file.content_type
    if content_type not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {content_type}"
        )
    
    # Create upload directory if it doesn't exist
    upload_dir = Path(settings.UPLOAD_DIR) / str(current_user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{timestamp}_{file.filename}"
    file_path = upload_dir / unique_filename
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Generate file URL
    file_url = f"/uploads/{current_user.id}/{unique_filename}"
    
    # Create file attachment record
    attachment = await FileAttachment.create(
        db,
        user_id=current_user.id,
        file_name=file.filename,
        file_path=str(file_path),
        file_url=file_url,
        file_type=content_type,
        file_size=file_size
    )
    
    # Create message with file attachment
    new_message = await Message.create(
        db,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=f"Sent a file: {file.filename}",
        has_attachment=True,
        file_url=file_url,
        file_type=content_type,
        file_name=file.filename,
        file_size=file_size,
        reply_to_id=reply_to_id
    )
    
    # Update file attachment with message ID
    await FileAttachment.update(
        db,
        attachment.id,
        message_id=new_message.id
    )
    
    # Notify receiver if online
    if connection_manager.is_user_connected(receiver_id):
        await connection_manager.send_message_notification(
            receiver_id,
            {
                "type": "new_file_message",
                "message": {
                    "id": new_message.id,
                    "sender_id": current_user.id,
                    "content": f"Sent a file: {file.filename}",
                    "created_at": new_message.created_at.isoformat(),
                    "has_attachment": True,
                    "file_url": file_url,
                    "file_type": content_type,
                    "file_name": file.filename,
                    "file_size": file_size,
                    "reply_to_id": reply_to_id
                }
            }
        )
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        current_user.id,
        ActivityType.UPLOAD_FILE,
        description=f"Uploaded file {file.filename} to user {receiver.username}"
    )
    
    return new_message

@router.get("/conversation/{user_id}", response_model=List[MessageResponse])
async def get_conversation(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    date_from: datetime = None,
    date_to: datetime = None,
    has_attachment: bool = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversation with another user with filters."""
    # Check if user exists
    other_user = await User.get_by_id(db, user_id)
    if not other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if users are friends
    friendship = await Friendship.get_friendship(db, current_user.id, user_id)
    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view conversations with friends"
        )
    
    # Get messages with filters
    messages = await Message.get_conversation(
        db,
        current_user.id,
        user_id,
        skip=skip,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        has_attachment=has_attachment
    )
    
    # Mark unread messages as read
    for message in messages:
        if message.receiver_id == current_user.id and not message.is_read:
            await Message.mark_as_read(db, message.id, current_user.id)
    
    return messages

@router.get("/search", response_model=List[MessageResponse])
async def search_messages(
    q: str,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Search for messages containing a specific term."""
    if len(q) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search term must be at least 3 characters"
        )
    
    messages = await Message.search_messages(
        db,
        current_user.id,
        q,
        skip=skip,
        limit=limit
    )
    
    return messages

@router.put("/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: int,
    message_update: MessageUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a message."""
    # Get message
    message = await Message.get_by_id(db, message_id)
    if not message or message.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Check if user is the sender
    if message.sender_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own messages"
        )
    
    # Update message
    updated_message = await Message.update(
        db,
        message_id,
        content=message_update.content,
        is_edited=True,
        edited_at=datetime.utcnow()
    )
    
    # Notify receiver if online
    if message.receiver_id and connection_manager.is_user_connected(message.receiver_id):
        await connection_manager.send_message_notification(
            message.receiver_id,
            {
                "type": "message_updated",
                "message": {
                    "id": message.id,
                    "content": message_update.content,
                    "is_edited": True
                }
            }
        )
    # For group messages
    elif message.group_id:
        # Notify all group members
        members = await GroupMember.get_group_members(db, message.group_id)
        for member in members:
            if member.user_id != current_user.id and connection_manager.is_user_connected(member.user_id):
                await connection_manager.send_message_notification(
                    member.user_id,
                    {
                        "type": "message_updated",
                        "message": {
                            "id": message.id,
                            "content": message_update.content,
                            "is_edited": True,
                            "group_id": message.group_id
                        }
                    }
                )
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        current_user.id,
        ActivityType.EDIT_MESSAGE,
        description=f"Edited message {message_id}"
    )
    
    return updated_message

@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a message."""
    # Get message
    message = await Message.get_by_id(db, message_id)
    if not message or message.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Check if user is the sender
    if message.sender_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own messages"
        )
    
    # Soft delete message
    await Message.update(
        db,
        message_id,
        is_deleted=True,
        deleted_at=datetime.utcnow()
    )
    
    # Notify receiver if online
    if message.receiver_id and connection_manager.is_user_connected(message.receiver_id):
        await connection_manager.send_message_notification(
            message.receiver_id,
            {
                "type": "message_deleted",
                "message_id": message.id
            }
        )
    # For group messages
    elif message.group_id:
        # Notify all group members
        members = await GroupMember.get_group_members(db, message.group_id)
        for member in members:
            if member.user_id != current_user.id and connection_manager.is_user_connected(member.user_id):
                await connection_manager.send_message_notification(
                    member.user_id,
                    {
                        "type": "message_deleted",
                        "message_id": message.id,
                        "group_id": message.group_id
                    }
                )
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        current_user.id,
        ActivityType.DELETE_MESSAGE,
        description=f"Deleted message {message_id}"
    )
    
    return None

@router.post("/{message_id}/forward", response_model=MessageResponse)
async def forward_message(
    message_id: int,
    forward_data: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Forward a message to another user."""
    # Get original message
    original_message = await Message.get_by_id(db, message_id)
    if not original_message or original_message.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Check if user has access to the original message
    if original_message.receiver_id == current_user.id or original_message.sender_id == current_user.id:
        # User is part of the conversation, can forward
        pass
    elif original_message.group_id:
        # Check if user is in the group
        is_member = await GroupMember.is_member(db, original_message.group_id, current_user.id)
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this message"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this message"
        )
    
    # Check if receiver exists
    receiver = await User.get_by_id(db, forward_data.receiver_id)
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found"
        )
    
    # Check if users are friends
    friendship = await Friendship.get_friendship(db, current_user.id, forward_data.receiver_id)
    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only forward messages to friends"
        )
    
    # Create forwarded message
    new_message = await Message.create(
        db,
        sender_id=current_user.id,
        receiver_id=forward_data.receiver_id,
        content=original_message.content,
        forwarded_from_id=message_id,
        has_attachment=original_message.has_attachment,
        file_url=original_message.file_url,
        file_type=original_message.file_type,
        file_name=original_message.file_name,
        file_size=original_message.file_size
    )
    
    # Notify receiver if online
    if connection_manager.is_user_connected(forward_data.receiver_id):
        await connection_manager.send_message_notification(
            forward_data.receiver_id,
            {
                "type": "new_message",
                "message": {
                    "id": new_message.id,
                    "sender_id": current_user.id,
                    "content": original_message.content,
                    "created_at": new_message.created_at.isoformat(),
                    "forwarded_from_id": message_id,
                    "has_attachment": original_message.has_attachment,
                    "file_url": original_message.file_url,
                    "file_type": original_message.file_type,
                    "file_name": original_message.file_name,
                    "file_size": original_message.file_size
                }
            }
        )
    
    return new_message
