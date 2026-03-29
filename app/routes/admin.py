"""Admin routes — privileged moderation and account management."""

from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_admin
from app.database import get_db
from app.models.discussion import Post, Thread
from app.models.portfolio import Holding
from app.models.saved_news import SavedNews
from app.models.user import Profile
from app.models.watchlist import WatchlistItem
from app.schemas.admin import AdminUserOut, BanUserRequest

router = APIRouter(prefix="/admin", tags=["admin"])


_SERVICE_ROLE_HEADERS = {
    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}


def _extract_supabase_error_message(payload: dict) -> str:
    return (
        payload.get("message")
        or payload.get("msg")
        or payload.get("error_description")
        or payload.get("error")
        or "Supabase request failed"
    )


def _parse_supabase_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    text = value.strip()
    if not text:
        return None

    # Supabase commonly returns UTC timestamps with trailing Z.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


async def _get_supabase_ban_lookup() -> dict[str, datetime | None]:
    url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            headers=_SERVICE_ROLE_HEADERS,
            params={"page": 1, "per_page": 1000},
        )

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch users from auth provider",
        )

    payload = resp.json()
    users = payload.get("users", []) if isinstance(payload, dict) else []
    lookup: dict[str, datetime | None] = {}

    for user_row in users:
        user_id = str(user_row.get("id") or "").strip()
        if not user_id:
            continue
        lookup[user_id] = _parse_supabase_datetime(user_row.get("banned_until"))

    return lookup


def _refresh_thread_stats(db: Session, thread: Thread) -> None:
    remaining_user_rows = (
        db.query(Post.user_id)
        .filter(Post.thread_id == thread.id)
        .distinct()
        .all()
    )
    remaining_post_count = db.query(Post).filter(Post.thread_id == thread.id).count()
    thread.message_count = remaining_post_count
    thread.participating_users = [str(user_id) for (user_id,) in remaining_user_rows]


def _delete_user_local_data(db: Session, user_id: str) -> None:
    posts_by_user_thread_ids = {
        thread_id
        for (thread_id,) in db.query(Post.thread_id).filter(Post.user_id == user_id).distinct().all()
    }

    db.query(Post).filter(Post.user_id == user_id).delete(synchronize_session=False)

    threads_created_by_user = db.query(Thread).filter(Thread.created_by == user_id).all()
    deleted_thread_ids = {thread.id for thread in threads_created_by_user}
    for thread in threads_created_by_user:
        db.delete(thread)

    remaining_thread_ids = posts_by_user_thread_ids - deleted_thread_ids
    for thread_id in remaining_thread_ids:
        thread = db.query(Thread).filter(Thread.id == thread_id).first()
        if thread:
            _refresh_thread_stats(db, thread)

    db.query(Holding).filter(Holding.user_id == user_id).delete(synchronize_session=False)
    db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id).delete(synchronize_session=False)
    db.query(SavedNews).filter(SavedNews.user_id == user_id).delete(synchronize_session=False)
    db.query(Profile).filter(Profile.id == user_id).delete(synchronize_session=False)


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    current_admin: Profile = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _ = current_admin
    profiles = db.query(Profile).order_by(Profile.created_at.desc()).all()
    ban_lookup = await _get_supabase_ban_lookup()

    return [
        AdminUserOut(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role or "user",
            created_at=user.created_at,
            banned_until=ban_lookup.get(str(user.id)),
        )
        for user in profiles
    ]


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: str,
    body: BanUserRequest,
    current_admin: Profile = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot ban yourself")

    profile = db.query(Profile).filter(Profile.id == user_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers=_SERVICE_ROLE_HEADERS,
            json={"ban_duration": body.ban_duration},
        )

    if resp.status_code >= 400:
        payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_extract_supabase_error_message(payload),
        )

    return {
        "message": "User banned successfully",
        "user_id": user_id,
        "ban_duration": body.ban_duration,
    }


@router.delete("/users/{user_id}/ban")
async def unban_user(
    user_id: str,
    current_admin: Profile = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot unban yourself")

    profile = db.query(Profile).filter(Profile.id == user_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers=_SERVICE_ROLE_HEADERS,
            json={"ban_duration": "none"},
        )

    if resp.status_code >= 400:
        payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_extract_supabase_error_message(payload),
        )

    return {"message": "User unbanned successfully", "user_id": user_id}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_account(
    user_id: str,
    current_admin: Profile = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete yourself")

    profile = db.query(Profile).filter(Profile.id == user_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers=_SERVICE_ROLE_HEADERS,
        )

    if resp.status_code >= 400:
        payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_extract_supabase_error_message(payload),
        )

    _delete_user_local_data(db, user_id)
    db.commit()


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_thread(
    thread_id: int,
    current_admin: Profile = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _ = current_admin
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    db.delete(thread)
    db.commit()


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_post(
    post_id: int,
    current_admin: Profile = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _ = current_admin
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    thread = db.query(Thread).filter(Thread.id == post.thread_id).first()
    db.delete(post)
    if thread:
        db.flush()
        _refresh_thread_stats(db, thread)
    db.commit()
