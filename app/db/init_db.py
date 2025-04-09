import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import async_session, engine
from app.models.user import User
from app.models.friendship import Friendship, FriendshipStatus
from app.models.message import Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Create initial data
    async with async_session() as db:
        await create_initial_data(db)

async def create_initial_data(db: AsyncSession):
    # Create test users
    logger.info("Creating test users...")
    
    # User 1
    user1 = await User.create(
        db,
        email="john@example.com",
        username="john_doe",
        hashed_password=hash_password("password123"),
        full_name="John Doe",
        status_message="Hello, I'm using ChatWave!",
        is_active=True,
        is_verified=True
    )
    
    # User 2
    user2 = await User.create(
        db,
        email="jane@example.com",
        username="jane_smith",
        hashed_password=hash_password("password123"),
        full_name="Jane Smith",
        status_message="Available",
        is_active=True,
        is_verified=True
    )
    
    # User 3
    user3 = await User.create(
        db,
        email="bob@example.com",
        username="bob_johnson",
        hashed_password=hash_password("password123"),
        full_name="Bob Johnson",
        is_active=True,
        is_verified=True
    )
    
    # Create friendships
    logger.info("Creating friendships...")
    
    # John and Jane are friends
    friendship1 = await Friendship.create(
        db,
        requester_id=user1.id,
        addressee_id=user2.id,
        status=FriendshipStatus.ACCEPTED
    )
    
    # Bob sent request to John
    friendship2 = await Friendship.create(
        db,
        requester_id=user3.id,
        addressee_id=user1.id,
        status=FriendshipStatus.PENDING
    )
    
    # Create some messages
    logger.info("Creating sample messages...")
    
    # Messages between John and Jane
    await Message.create(
        db,
        sender_id=user1.id,
        receiver_id=user2.id,
        content="Hey Jane, how are you?"
    )
    
    await Message.create(
        db,
        sender_id=user2.id,
        receiver_id=user1.id,
        content="I'm good, thanks! How about you?"
    )
    
    await Message.create(
        db,
        sender_id=user1.id,
        receiver_id=user2.id,
        content="Doing well. Want to try the new video call feature?"
    )
    
    logger.info("Initial data created successfully!")

if __name__ == "__main__":
    asyncio.run(init_db())
