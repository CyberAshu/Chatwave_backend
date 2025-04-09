import asyncio
import logging
import uvicorn

from app.db.init_db import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")

if __name__ == "__main__":
    # Initialize the database
    asyncio.run(main())
    
    # Run the application
    logger.info("Starting application")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
