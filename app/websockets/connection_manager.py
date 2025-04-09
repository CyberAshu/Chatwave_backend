import json
import asyncio
from typing import Dict, List, Set

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.models.user import User
from app.models.group import GroupMember
from app.models.group import Group
from app.models.message import Message

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Map of user_id to WebSocket connection
        self.active_connections: Dict[int, WebSocket] = {}
        # Map of user_id to set of user_ids they're subscribed to
        self.subscriptions: Dict[int, Set[int]] = {}
        # Map of group_id to set of user_ids connected to that group
        self.group_connections: Dict[int, Set[int]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.subscriptions[user_id] = set()
        
        # Notify friends that user is online
        await self.broadcast_status(user_id, True)
    
    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        if user_id in self.subscriptions:
            del self.subscriptions[user_id]
        
        # Remove user from all subscriptions
        for user_subs in self.subscriptions.values():
            if user_id in user_subs:
                user_subs.remove(user_id)
        
        # Remove user from all group connections
        for group_id, members in self.group_connections.items():
            if user_id in members:
                members.remove(user_id)
        
        # Notify friends that user is offline
        asyncio.create_task(self.broadcast_status(user_id, False))
    
    def is_user_connected(self, user_id: int) -> bool:
        return user_id in self.active_connections
    
    async def subscribe_to_user(self, subscriber_id: int, target_id: int):
        """Subscribe to a user's status updates."""
        if subscriber_id in self.subscriptions:
            self.subscriptions[subscriber_id].add(target_id)
    
    async def unsubscribe_from_user(self, subscriber_id: int, target_id: int):
        """Unsubscribe from a user's status updates."""
        if subscriber_id in self.subscriptions and target_id in self.subscriptions[subscriber_id]:
            self.subscriptions[subscriber_id].remove(target_id)
    
    async def join_group(self, user_id: int, group_id: int):
        """Join a group chat room."""
        if group_id not in self.group_connections:
            self.group_connections[group_id] = set()
        
        self.group_connections[group_id].add(user_id)
        
        # Notify other group members that user joined
        await self.broadcast_to_group(
            group_id,
            {
                "type": "group_join",
                "user_id": user_id,
                "group_id": group_id
            },
            exclude_user_id=user_id
        )
    
    async def leave_group(self, user_id: int, group_id: int):
        """Leave a group chat room."""
        if group_id in self.group_connections and user_id in self.group_connections[group_id]:
            self.group_connections[group_id].remove(user_id)
            
            # Notify other group members that user left
            await self.broadcast_to_group(
                group_id,
                {
                    "type": "group_leave",
                    "user_id": user_id,
                    "group_id": group_id
                },
                exclude_user_id=user_id
            )
    
    async def send_personal_message(self, user_id: int, message: str):
        """Send a message to a specific user."""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)
    
    async def broadcast_status(self, user_id: int, is_online: bool):
        """Broadcast user status to all subscribers."""
        subscribers = []
        for subscriber_id, subscribed_to in self.subscriptions.items():
            if user_id in subscribed_to:
                subscribers.append(subscriber_id)
        
        status_message = {
            "type": "status_update",
            "user_id": user_id,
            "is_online": is_online
        }
        
        for subscriber_id in subscribers:
            if subscriber_id in self.active_connections:
                await self.active_connections[subscriber_id].send_json(status_message)
     
                await self.active_connections[subscriber_id].send_json(status_message)
    
    async def send_message_notification(self, user_id: int, data: dict):
        """Send a message notification to a specific user."""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(data)
    
    async def send_call_notification(self, user_id: int, data: dict):
        """Send a call notification to a specific user."""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(data)
    
    async def send_typing_indicator(self, from_user_id: int, to_user_id: int, is_typing: bool):
        """Send typing indicator to a specific user."""
        if to_user_id in self.active_connections:
            await self.active_connections[to_user_id].send_json({
                "type": "typing_indicator",
                "user_id": from_user_id,
                "is_typing": is_typing
            })
    
    async def broadcast_to_group(self, group_id: int, data: dict, exclude_user_id: int = None):
        """Broadcast a message to all members of a group."""
        if group_id in self.group_connections:
            for user_id in self.group_connections[group_id]:
                if exclude_user_id is None or user_id != exclude_user_id:
                    if user_id in self.active_connections:
                        await self.active_connections[user_id].send_json(data)

connection_manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    # Verify user exists
    user = await User.get_by_id(db, user_id)
    if not user:
        await websocket.close(code=4004)
        return
    
    # Accept connection
    await connection_manager.connect(websocket, user_id)
    
    # Update user's last seen
    await User.update_last_seen(db, user_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Handle different message types
            if data["type"] == "subscribe":
                target_id = data.get("user_id")
                if target_id:
                    await connection_manager.subscribe_to_user(user_id, target_id)
            
            elif data["type"] == "unsubscribe":
                target_id = data.get("user_id")
                if target_id:
                    await connection_manager.unsubscribe_from_user(user_id, target_id)
            
            elif data["type"] == "typing":
                to_user_id = data.get("to_user_id")
                is_typing = data.get("is_typing", False)
                if to_user_id:
                    await connection_manager.send_typing_indicator(user_id, to_user_id, is_typing)
            
            elif data["type"] == "join_group":
                group_id = data.get("group_id")
                if group_id:
                    # Verify user is a member of the group
                    is_member = await GroupMember.is_member(db, group_id, user_id)
                    if is_member:
                        await connection_manager.join_group(user_id, group_id)
            
            elif data["type"] == "leave_group":
                group_id = data.get("group_id")
                if group_id:
                    await connection_manager.leave_group(user_id, group_id)
            
            # Heartbeat to keep connection alive
            elif data["type"] == "ping":
                await websocket.send_json({"type": "pong"})
                
                # Update last seen on ping
                await User.update_last_seen(db, user_id)
    
    except WebSocketDisconnect:
        connection_manager.disconnect(user_id)
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        connection_manager.disconnect(user_id)

@router.websocket("/ws/group/{group_id}")
async def group_websocket_endpoint(
    websocket: WebSocket,
    group_id: int,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """WebSocket endpoint for group chats."""
    # Verify user exists
    user = await User.get_by_id(db, user_id)
    if not user:
        await websocket.close(code=4004)
        return
    
    # Verify group exists
    group = await Group.get_by_id(db, group_id)
    if not group:
        await websocket.close(code=4004)
        return
    
    # Verify user is a member of the group
    is_member = await GroupMember.is_member(db, group_id, user_id)
    if not is_member:
        await websocket.close(code=4003)
        return
    
    # Accept connection
    await websocket.accept()
    
    # Add user to group connections
    if group_id not in connection_manager.group_connections:
        connection_manager.group_connections[group_id] = set()
    
    connection_manager.group_connections[group_id].add(user_id)
    
    # Notify other group members that user joined
    await connection_manager.broadcast_to_group(
        group_id,
        {
            "type": "group_join",
            "user_id": user_id,
            "group_id": group_id
        },
        exclude_user_id=user_id
    )
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Handle different message types
            if data["type"] == "group_message":
                content = data.get("content")
                if content:
                    # Create message in database
                    new_message = await Message.create(
                        db,
                        sender_id=user_id,
                        group_id=group_id,
                        content=content,
                        receiver_id=None
                    )
                    
                    # Broadcast to all group members
                    await connection_manager.broadcast_to_group(
                        group_id,
                        {
                            "type": "new_group_message",
                            "message": {
                                "id": new_message.id,
                                "sender_id": user_id,
                                "group_id": group_id,
                                "content": content,
                                "created_at": new_message.created_at.isoformat()
                            }
                        }
                    )
            
            elif data["type"] == "group_typing":
                is_typing = data.get("is_typing", False)
                # Broadcast typing indicator to all group members
                await connection_manager.broadcast_to_group(
                    group_id,
                    {
                        "type": "group_typing",
                        "user_id": user_id,
                        "group_id": group_id,
                        "is_typing": is_typing
                    },
                    exclude_user_id=user_id
                )
            
            # Heartbeat to keep connection alive
            elif data["type"] == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        # Remove user from group connections
        if group_id in connection_manager.group_connections and user_id in connection_manager.group_connections[group_id]:
            connection_manager.group_connections[group_id].remove(user_id)
            
            # Notify other group members that user left
            await connection_manager.broadcast_to_group(
                group_id,
                {
                    "type": "group_leave",
                    "user_id": user_id,
                    "group_id": group_id
                }
            )
    
    except Exception as e:
        print(f"Group WebSocket error: {str(e)}")
        # Remove user from group connections
        if group_id in connection_manager.group_connections and user_id in connection_manager.group_connections[group_id]:
            connection_manager.group_connections[group_id].remove(user_id)
