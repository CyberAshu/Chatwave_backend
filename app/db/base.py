from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
from sqlalchemy import update, delete

Base = declarative_base()

class CRUDBase:
    """Base class for CRUD operations."""
    
    @classmethod
    async def get_by_id(cls, db: AsyncSession, id: int):
        """Get a record by ID."""
        result = await db.execute(select(cls).where(cls.id == id))
        return result.scalars().first()
    
    @classmethod
    async def get_all(cls, db: AsyncSession, skip: int = 0, limit: int = 100):
        """Get all records with pagination."""
        result = await db.execute(select(cls).offset(skip).limit(limit))
        return result.scalars().all()
    
    @classmethod
    async def create(cls, db: AsyncSession, **kwargs):
        """Create a new record."""
        obj = cls(**kwargs)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj
    
    @classmethod
    async def update(cls, db: AsyncSession, id: int, **kwargs):
        """Update a record."""
        await db.execute(update(cls).where(cls.id == id).values(**kwargs))
        await db.commit()
        return await cls.get_by_id(db, id)
    
    @classmethod
    async def delete(cls, db: AsyncSession, id: int):
        """Delete a record."""
        await db.execute(delete(cls).where(cls.id == id))
        await db.commit()
        return True
