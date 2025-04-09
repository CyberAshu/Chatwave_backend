from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.dependencies import get_db, get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_password_reset_token,
    hash_password,
    verify_password,
    verify_token,
    generate_verification_token,
    validate_password_strength,
    generate_2fa_secret,
    verify_2fa_code
)
from app.core.email import email_client
from app.models.user import User
from app.models.activity_log import ActivityLog, ActivityType
from app.schemas.token import RefreshToken, Token, TokenPayload, TwoFactorToken
from app.schemas.user import UserCreate, UserResponse, VerifyEmail, ResetPassword, RequestPasswordReset

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def register(
    user_data: UserCreate, 
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user with email verification."""
    # Check if email already exists
    db_user = await User.get_by_email(db, user_data.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    db_user = await User.get_by_username(db, user_data.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Validate password strength
    if not validate_password_strength(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password does not meet security requirements"
        )
    
    # Create verification token
    verification_token = generate_verification_token()
    token_expires = datetime.utcnow() + timedelta(hours=settings.VERIFICATION_TOKEN_EXPIRE_HOURS)
    
    # Create new user
    hashed_password = hash_password(user_data.password)
    user_in_db = await User.create(
        db,
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_active=True,  # User is active but not verified
        is_verified=False,
        verification_token=verification_token,
        verification_token_expires=token_expires
    )
    
    # Send verification email
    await email_client.send_verification_email(
        user_data.email,
        user_data.username,
        verification_token
    )
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        user_in_db.id,
        ActivityType.REGISTER,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return user_in_db

@router.post("/verify-email", response_model=UserResponse)
async def verify_email(
    verification_data: VerifyEmail,
    db: AsyncSession = Depends(get_db)
):
    """Verify a user's email address."""
    user = await User.get_by_verification_token(db, verification_data.token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid verification token"
        )
    
    # Check if token is expired
    if user.verification_token_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired"
        )
    
    # Mark user as verified
    updated_user = await User.update(
        db,
        user.id,
        is_verified=True,
        verification_token=None,
        verification_token_expires=None
    )
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        user.id,
        ActivityType.EMAIL_VERIFIED
    )
    
    return updated_user

@router.post("/login", response_model=Token)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # Check if user exists
    user = await User.get_by_email(db, form_data.username)
    if not user:
        user = await User.get_by_username(db, form_data.username)
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    # Check if user is verified
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified"
        )
    
    # Check if 2FA is enabled
    if user.two_factor_enabled:
        # Return a temporary token for 2FA verification
        temp_token = create_access_token(
            data={"sub": str(user.id), "temp": True},
            expires_delta=timedelta(minutes=5)  # Short expiration for 2FA
        )
        
        return {
            "access_token": temp_token,
            "refresh_token": "",
            "token_type": "bearer",
            "requires_2fa": True
        }
    
    # Update last seen
    await User.update_last_seen(db, user.id)
    
    # Create access and refresh tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Log activity
    await ActivityLog.log_activity(
        db,
        user.id,
        ActivityType.LOGIN,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "requires_2fa": False
    }

@router.post("/2fa/verify", response_model=Token)
async def verify_2fa(
    token_data: TwoFactorToken,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Verify 2FA code and complete login."""
    try:
        # Verify the temporary token
        payload = verify_token(token_data.temp_token)
        user_id = payload.get("sub")
        is_temp = payload.get("temp", False)
        
        if not user_id or not is_temp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = await User.get_by_id(db, int(user_id))
        if not user or not user.is_active or not user.is_verified or not user.two_factor_enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify 2FA code
        if not verify_2fa_code(user.two_factor_secret, token_data.code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Update last seen
        await User.update_last_seen(db, user.id)
        
        # Create access and refresh tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )
        
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        # Log activity
        await ActivityLog.log_activity(
            db,
            user.id,
            ActivityType.LOGIN,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "requires_2fa": False
        }
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA verification",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/refresh", response_model=Token)
async def refresh_token_endpoint(
    token_data: RefreshToken,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    try:
        payload = verify_token(token_data.refresh_token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = await User.get_by_id(db, int(user_id))
        if not user or not user.is_active or not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user or inactive user",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create new tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )
        
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "requires_2fa": False
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Log out a user."""
    # In a stateless JWT system, we can't invalidate tokens
    # But we can log the logout for tracking purposes
    
    await ActivityLog.log_activity(
        db,
        current_user.id,
        ActivityType.LOGOUT,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return {"detail": "Successfully logged out"}

@router.post("/request-password-reset")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def request_password_reset(
    reset_request: RequestPasswordReset,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Request a password reset."""
    # Find user by email
    user = await User.get_by_email(db, reset_request.email)
    
    # Always return success to prevent email enumeration
    if not user:
        return {"detail": "If the email exists, a password reset link has been sent"}
    
    # Generate reset token
    reset_token = generate_password_reset_token()
    token_expires = datetime.utcnow() + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    
    # Update user with reset token
    await User.update(
        db,
        user.id,
        password_reset_token=reset_token,
        password_reset_expires=token_expires
    )
    
    # Send password reset email
    await email_client.send_password_reset_email(
        user.email,
        user.username,
        reset_token
    )
    
    return {"detail": "If the email exists, a password reset link has been sent"}

@router.post("/reset-password")
async def reset_password(
    reset_data: ResetPassword,
    db: AsyncSession = Depends(get_db)
):
    """Reset a user's password using a reset token."""
    # Find user by reset token
    user = await User.get_by_reset_token(db, reset_data.token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid reset token"
        )
    
    # Check if token is expired
    if user.password_reset_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )
    
    # Validate password strength
    if not validate_password_strength(reset_data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password does not meet security requirements"
        )
    
    # Update password
    hashed_password = hash_password(reset_data.new_password)
    await User.update(
        db,
        user.id,
        hashed_password=hashed_password,
        password_reset_token=None,
        password_reset_expires=None
    )
    
    return {"detail": "Password has been reset successfully"}

@router.post("/2fa/setup", response_model=dict)
async def setup_2fa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set up 2FA for a user."""
    # Generate 2FA secret
    secret = generate_2fa_secret()
    
    # Update user with 2FA secret (not enabled yet)
    await User.update(
        db,
        current_user.id,
        two_factor_secret=secret
    )
    
    # Generate provisioning URI for QR code
    provisioning_uri = get_2fa_provisioning_uri(secret, current_user.email)
    
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri
    }

@router.post("/2fa/enable")
async def enable_2fa(
    token_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Enable 2FA for a user after verification."""
    # Verify the provided code
    if not verify_2fa_code(current_user.two_factor_secret, token_data.get("code")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )
    
    # Enable 2FA
    await User.update(
        db,
        current_user.id,
        two_factor_enabled=True
    )
    
    return {"detail": "Two-factor authentication has been enabled"}

@router.post("/2fa/disable")
async def disable_2fa(
    token_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disable 2FA for a user."""
    # Verify the provided code
    if not verify_2fa_code(current_user.two_factor_secret, token_data.get("code")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )
    
    # Disable 2FA
    await User.update(
        db,
        current_user.id,
        two_factor_enabled=False,
        two_factor_secret=None
    )
    
    return {"detail": "Two-factor authentication has been disabled"}
