import os
from typing import List
from pydantic import AnyHttpUrl, EmailStr
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ChatWave"
    
    # CORS
    CORS_ORIGINS: List[AnyHttpUrl] = ["http://localhost:3000"]
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:12345@localhost:5432/chatwave")
    
    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "supersecretkey")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Security
    PASSWORD_HASH_ROUNDS: int = 12
    
    # Email verification
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 48
    
    # Password reset
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Rate limiting
    LOGIN_RATE_LIMIT: str = "5/minute"
    REGISTER_RATE_LIMIT: str = "3/minute"
    MESSAGE_RATE_LIMIT: str = "30/minute"
    
    # Email settings
    EMAIL_SENDER: EmailStr = "noreply@chatwave.com"
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.example.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = True
    
    # Frontend URL for email links
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # File upload settings
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_FILE_TYPES: List[str] = [
        "image/jpeg", "image/png", "image/gif", 
        "application/pdf", "application/msword", 
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain", "application/zip"
    ]
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
