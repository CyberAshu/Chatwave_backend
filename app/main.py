from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth, users, friends, messages, calls, groups, admin
from app.core.config import settings
from app.core.dependencies import get_db
from app.websockets.connection_manager import router as websocket_router

# Create limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="ChatWave API",
    description="Real-time chat application API",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(friends.router, prefix="/api/friends", tags=["Friends"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])
app.include_router(calls.router, prefix="/api/calls", tags=["Calls"])
app.include_router(groups.router, prefix="/api/groups", tags=["Groups"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(websocket_router)

@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "healthy", "app": "ChatWave"}

@app.get("/api/health", tags=["Health"])
async def api_health_check(db: AsyncSession = Depends(get_db)):
    try:
        # Check database connection
        await db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection error: {str(e)}"
        )

# Middleware to log request information
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Process the request
    response = await call_next(request)
    
    # You could log request information here
    # For example, to a database or file
    
    return response
