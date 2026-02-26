"""Auth routes — proxies register/login to Supabase GoTrue, manages local Profile."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import Profile
from app.schemas.auth import Token, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

GOTRUE_HEADERS = {
    "apikey": settings.SUPABASE_ANON_KEY,
    "Content-Type": "application/json",
}


@router.post("/register", response_model=Token)
async def register(body: UserCreate, db: Session = Depends(get_db)):
    """Register a new user via Supabase Auth, then create a local Profile."""

    # Check if username is already taken locally
    existing = db.query(Profile).filter(Profile.username == body.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Call Supabase GoTrue signup
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/signup",
            headers=GOTRUE_HEADERS,
            json={
                "email": body.email,
                "password": body.password,
                "data": {"username": body.username},
            },
        )

    data = resp.json()

    if resp.status_code >= 400:
        detail = data.get("msg") or data.get("error_description") or data.get("message", "Registration failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    user_data = data.get("user", data)
    session_data = data.get("session")

    user_id = user_data.get("id")
    access_token = (session_data or {}).get("access_token")

    if not user_id or not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected response from auth provider",
        )

    # Create local profile
    profile = Profile(
        id=user_id,
        username=body.username,
        email=body.email,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return Token(
        access_token=access_token,
        user=UserOut.model_validate(profile),
    )


@router.post("/login", response_model=Token)
async def login(body: UserLogin, db: Session = Depends(get_db)):
    """Log in via Supabase Auth and return the access token."""

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers=GOTRUE_HEADERS,
            json={
                "email": body.email,
                "password": body.password,
            },
        )

    data = resp.json()

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_data = data.get("user", {})
    user_id = user_data.get("id")
    access_token = data.get("access_token")

    if not user_id or not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected response from auth provider",
        )

    # Ensure a local profile exists (handles edge case: user in Supabase but no profile)
    profile = db.query(Profile).filter(Profile.id == user_id).first()
    if not profile:
        email = user_data.get("email", body.email)
        username = (user_data.get("user_metadata") or {}).get("username", email.split("@")[0])
        profile = Profile(id=user_id, username=username, email=email)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return Token(
        access_token=access_token,
        user=UserOut.model_validate(profile),
    )


@router.get("/me", response_model=UserOut)
def me(current_user: Profile = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserOut.model_validate(current_user)
