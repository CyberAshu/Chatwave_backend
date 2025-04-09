from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator

from app.models.user import UserRole

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    
    class Config:
        from_attributes = True

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    
    @validator('password')
    def password_strength(cls, v):
        # Simple password strength check
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c.isalpha() for c in v):
            raise ValueError('Password must contain at least one letter')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/" for c in v):
            raise ValueError('Password must contain at least one special character')
        return v

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    status_message: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    show_online_status: Optional[bool] = None
    show_last_seen: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    full_name: Optional[str] = None
    status_message: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: str
    is_active: bool
    is_verified: bool
    role: UserRole
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    
    # Only include these if the user's privacy settings allow
    online_status: Optional[bool] = None
    last_seen: Optional[datetime] = None

class UserInDB(UserBase):
    id: int
    hashed_password: str
    full_name: Optional[str] = None
    status_message: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: str
    is_active: bool
    is_verified: bool
    role: UserRole
    show_online_status: bool
    show_last_seen: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime
    
    # Two-factor authentication
    two_factor_enabled: bool
    two_factor_secret: Optional[str] = None

class VerifyEmail(BaseModel):
    token: str

class RequestPasswordReset(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    token: str
    new_password: str
