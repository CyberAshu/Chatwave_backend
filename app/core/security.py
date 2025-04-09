from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import secrets
import uuid

import bcrypt
from jose import jwt
import pyotp

from app.core.config import settings

def hash_password(password: str) -> str:
    """Hash a password for storing."""
    salt = bcrypt.gensalt(rounds=settings.PASSWORD_HASH_ROUNDS)
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a stored password against a provided password."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a new access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET, 
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a new refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET, 
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    """Verify a JWT token and return its payload."""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM]
    )
    return payload

def generate_verification_token() -> str:
    """Generate a token for email verification."""
    return str(uuid.uuid4())

def generate_password_reset_token() -> str:
    """Generate a token for password reset."""
    return secrets.token_urlsafe(32)

def generate_2fa_secret() -> str:
    """Generate a secret for 2FA."""
    return pyotp.random_base32()

def verify_2fa_code(secret: str, code: str) -> bool:
    """Verify a 2FA code."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

def get_2fa_provisioning_uri(secret: str, email: str) -> str:
    """Get the provisioning URI for 2FA setup."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name="ChatWave")

def validate_password_strength(password: str) -> bool:
    """
    Validate password strength.
    
    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if len(password) < 8:
        return False
    
    if not any(c.isupper() for c in password):
        return False
        
    if not any(c.islower() for c in password):
        return False
        
    if not any(c.isdigit() for c in password):
        return False
        
    if not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/" for c in password):
        return False
        
    return True
