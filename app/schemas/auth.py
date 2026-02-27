"""Pydantic schemas for authentication (register, login, token)."""

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """Request body for POST /auth/register."""
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """Request body for POST /auth/login."""
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Safe user representation (no password)."""
    id: str
    username: str
    email: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Response for login and register."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfileUpdate(BaseModel):
    """Request body for PATCH /auth/profile."""
    username: str
    email: EmailStr


class PasswordChange(BaseModel):
    """Request body for PATCH /auth/password."""
    current_password: str
    new_password: str
