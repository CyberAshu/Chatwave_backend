from typing import Optional, Union

from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    requires_2fa: bool = False

class TokenPayload(BaseModel):
    user_id: int
    exp: Optional[int] = None
    temp: Optional[bool] = None

class RefreshToken(BaseModel):
    refresh_token: str

class TwoFactorToken(BaseModel):
    temp_token: str
    code: str
