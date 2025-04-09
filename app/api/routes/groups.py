from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from app.core.dependencies import get_current_active_user, get_db
from app.models.group import Group, GroupMember, GroupMemberRole
from app.models.message import Message
from app.models.user import User
from app.models.activity_log import ActivityLog, ActivityType
from app.schemas.group import (
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    GroupMemberResponse,
    GroupInvite
)
from app.schemas.message import MessageCreate, MessageResponse
from app.websockets import connection_manager

router = APIRouter()

@router.post("/create", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new group chat."""
    # Verify user is verified
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    
    # Create the group
    group = await Group.create(
        db,
        name=group_data.name,
        description=group_data.description,
        avatar_url=group_data.avatar_url,
        created_by=current_user.id
    )
    
    # Add creator as admin
    await GroupMember.create(
        db,
        group_id=group.id,
        user_id=current_user.id,
        role=GroupMemberRole.ADMIN
    )
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        current_user.id,
        ActivityType.CREATE_GROUP,
        description=f"Created group: {group.name}"
    )
    
    return group

@router.get("/", response_model=List[GroupResponse])
async def get_user_groups(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all groups the current user is a member of."""
    groups = await Group.get_user_groups(db, current_user.id)
    return groups

@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific group."""
    # Check if group exists
    group = await Group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user is a member
    is_member = await GroupMember.is_member(db, group_id, current_user.id)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group"
        )
    
    return group

@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    group_data: GroupUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a group."""
    # Check if group exists
    group = await Group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user is an admin
    is_admin = await GroupMember.is_admin(db, group_id, current_user.id)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only group admins can update group details"
        )
    
    # Update group
    updated_group = await Group.update(
        db,
        group_id,
        **group_data.dict(exclude_unset=True)
    )
    
    return updated_group

@router.post("/{group_id}/invite", status_code=status.HTTP_201_CREATED)
async def invite_to_group(
    group_id: int,
    invite_data: GroupInvite,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Invite a user to a group."""
    # Check if group exists
    group = await Group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user is a member with invite permissions (admin)
    is_admin = await GroupMember.is_admin(db, group_id, current_user.id)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only group admins can invite users"
        )
    
    # Check if invited user exists
    invited_user = await User.get_by_id(db, invite_data.user_id)
    if not invited_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user is already a member
    is_already_member = await GroupMember.is_member(db, group_id, invite_data.user_id)
    if is_already_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this group"
        )
    
    # Add user to group
    await GroupMember.create(
        db,
        group_id=group_id,
        user_id=invite_data.user_id,
        role=GroupMemberRole.MEMBER
    )
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        current_user.id,
        ActivityType.JOIN_GROUP,
        description=f"Added user {invited_user.username} to group {group.name}"
    )
    
    return {"detail": f"User {invited_user.username} has been added to the group"}

@router.get("/{group_id}/members", response_model=List[GroupMemberResponse])
async def get_group_members(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all members of a group."""
    # Check if group exists
    group = await Group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user is a member
    is_member = await GroupMember.is_member(db, group_id, current_user.id)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group"
        )
    
    # Get members
    members = await GroupMember.get_group_members(db, group_id)
    
    # Enrich with user information
    result = []
    for member in members:
        user = await User.get_by_id(db, member.user_id)
        if user:
            result.append(
                GroupMemberResponse(
                    id=member.id,
                    user_id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                    avatar_url=user.avatar_url,
                    role=member.role,
                    joined_at=member.joined_at
                )
            )
    
    return result

@router.delete("/{group_id}/leave")
async def leave_group(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Leave a group."""
    # Check if group exists
    group = await Group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user is a member
    membership = await db.execute(
        select(GroupMember).where(
            (GroupMember.group_id == group_id) & 
            (GroupMember.user_id == current_user.id) &
            (GroupMember.is_active == True)
        )
    )
    membership = membership.scalars().first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group"
        )
    
    # Check if user is the only admin
    if membership.role == GroupMemberRole.ADMIN:
        admin_count = await db.execute(
            select(func.count()).where(
                (GroupMember.group_id == group_id) & 
                (GroupMember.role == GroupMemberRole.ADMIN) &
                (GroupMember.is_active == True)
            )
        )
        admin_count = admin_count.scalar()
        
        if admin_count == 1:
            # Check if there are other members
            member_count = await db.execute(
                select(func.count()).where(
                    (GroupMember.group_id == group_id) & 
                    (GroupMember.is_active == True)
                )
            )
            member_count = member_count.scalar()
            
            if member_count > 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You are the only admin. Promote another member to admin before leaving."
                )
    
    # Soft delete membership (set is_active to False)
    await GroupMember.update(
        db,
        membership.id,
        is_active=False
    )
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        current_user.id,
        ActivityType.LEAVE_GROUP,
        description=f"Left group: {group.name}"
    )
    
    return {"detail": "You have left the group"}

@router.post("/{group_id}/promote/{user_id}")
async def promote_to_admin(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Promote a group member to admin."""
    # Check if group exists
    group = await Group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if current user is an admin
    is_admin = await GroupMember.is_admin(db, group_id, current_user.id)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only group admins can promote members"
        )
    
    # Check if target user is a member
    target_membership = await db.execute(
        select(GroupMember).where(
            (GroupMember.group_id == group_id) & 
            (GroupMember.user_id == user_id) &
            (GroupMember.is_active == True)
        )
    )
    target_membership = target_membership.scalars().first()
    
    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this group"
        )
    
    # Check if already an admin
    if target_membership.role == GroupMemberRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already an admin"
        )
    
    # Promote to admin
    await GroupMember.update(
        db,
        target_membership.id,
        role=GroupMemberRole.ADMIN
    )
    
    return {"detail": "User has been promoted to admin"}

@router.post("/{group_id}/messages", response_model=MessageResponse)
async def send_group_message(
    group_id: int,
    message: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message to a group."""
    # Check if group exists
    group = await Group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user is a member
    is_member = await GroupMember.is_member(db, group_id, current_user.id)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group"
        )
    
    # Create message
    new_message = await Message.create(
        db,
        sender_id=current_user.id,
        group_id=group_id,
        content=message.content,
        # For group messages, receiver_id is null
        receiver_id=None
    )
    
    # Notify group members via WebSocket
    members = await GroupMember.get_group_members(db, group_id)
    for member in members:
        if member.user_id != current_user.id and connection_manager.is_user_connected(member.user_id):
            await connection_manager.send_message_notification(
                member.user_id,
                {
                    "type": "new_group_message",
                    "message": {
                        "id": new_message.id,
                        "sender_id": current_user.id,
                        "group_id": group_id,
                        "content": message.content,
                        "created_at": new_message.created_at.isoformat()
                    }
                }
            )
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        current_user.id,
        ActivityType.SEND_MESSAGE,
        description=f"Sent message to group: {group.name}"
    )
    
    return new_message

@router.get("/{group_id}/messages", response_model=List[MessageResponse])
async def get_group_messages(
    group_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get messages from a group."""
    # Check if group exists
    group = await Group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user is a member
    is_member = await GroupMember.is_member(db, group_id, current_user.id)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group"
        )
    
    # Get messages
    query = select(Message).where(
        (Message.group_id == group_id) & 
        (Message.is_deleted == False)
    )
    
    query = query.order_by(Message.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # Mark messages as read for this user
    for message in messages:
        if message.sender_id != current_user.id:
            await Message.mark_as_read(db, message.id, current_user.id)
    
    return messages
