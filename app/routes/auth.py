"""Auth routes — proxies register/login to Supabase GoTrue, manages local Profile."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models.portfolio import Holding
from app.models.user import Profile
from app.models.watchlist import WatchlistItem
from app.core.security import get_current_user, oauth2_scheme
from app.schemas.auth import PasswordChange, ProfileUpdate, Token, UserCreate, UserLogin, UserOut

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
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected response from auth provider",
        )

    access_token = (session_data or {}).get("access_token")

    # If Supabase didn't return a session, log in to get a token
    if not access_token:
        async with httpx.AsyncClient() as client:
            login_resp = await client.post(
                f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password",
                headers=GOTRUE_HEADERS,
                json={"email": body.email, "password": body.password},
            )
        if login_resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="User created but could not obtain access token. Try logging in.",
            )
        access_token = login_resp.json().get("access_token")

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


@router.patch("/profile", response_model=UserOut)
async def update_profile(
    body: ProfileUpdate,
    token: str = Depends(oauth2_scheme),
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the user's username and/or email."""
    # Check username uniqueness (if changed)
    if body.username != current_user.username:
        taken = db.query(Profile).filter(Profile.username == body.username).first()
        if taken:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

    # If email changed, update it in Supabase too
    if body.email != current_user.email:
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{settings.SUPABASE_URL}/auth/v1/user",
                headers={**GOTRUE_HEADERS, "Authorization": f"Bearer {token}"},
                json={"email": body.email},
            )
        if resp.status_code >= 400:
            detail = resp.json().get("message", "Failed to update email")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    current_user.username = body.username
    current_user.email = body.email
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)


@router.patch("/password")
async def change_password(
    body: PasswordChange,
    token: str = Depends(oauth2_scheme),
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the user's password after verifying the current one."""
    # Verify current password by attempting a login
    async with httpx.AsyncClient() as client:
        verify_resp = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers=GOTRUE_HEADERS,
            json={"email": current_user.email, "password": body.current_password},
        )
    if verify_resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password in Supabase
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={**GOTRUE_HEADERS, "Authorization": f"Bearer {token}"},
            json={"password": body.new_password},
        )
    if resp.status_code >= 400:
        detail = resp.json().get("message", "Failed to update password")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    return {"message": "Password updated successfully"}


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently delete the user's account and all associated data."""
    user_id = current_user.id

    # Delete local data
    db.query(Holding).filter(Holding.user_id == user_id).delete()
    db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id).delete()
    db.query(Profile).filter(Profile.id == user_id).delete()
    db.commit()

    # Delete user from Supabase Auth (requires service role key)
    async with httpx.AsyncClient() as client:
        await client.delete(
            f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers={
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            },
        )
