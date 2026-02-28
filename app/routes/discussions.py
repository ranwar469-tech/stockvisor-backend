"""Discussion routes — threads and posts backed by the database."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.discussion import Post, Thread
from app.models.user import Profile
from app.schemas.discussions import (
    PostCreate,
    PostOut,
    PostUpdate,
    ThreadCreate,
    ThreadDetailOut,
    ThreadOut,
    ThreadUpdate,
)

router = APIRouter(prefix="/discussions", tags=["discussions"])


def _normalize_participants(raw_participants) -> List[str]:
    if isinstance(raw_participants, list):
        return [str(user_id) for user_id in raw_participants]
    return []


def _resolve_usernames(db: Session, user_ids: List[str]) -> dict[str, str]:
    if not user_ids:
        return {}

    rows = db.query(Profile.id, Profile.username).filter(Profile.id.in_(set(user_ids))).all()
    return {str(profile_id): username for profile_id, username in rows}


def _to_thread_out(thread: Thread, username_lookup: Optional[dict[str, str]] = None) -> ThreadOut:
    usernames = username_lookup or {}
    return ThreadOut(
        id=thread.id,
        category=thread.category,
        title=thread.title,
        created_by=thread.created_by,
        created_by_username=usernames.get(str(thread.created_by), str(thread.created_by)),
        message_count=thread.message_count,
        participating_users=_normalize_participants(thread.participating_users),
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


def _to_post_out(post: Post, username_lookup: Optional[dict[str, str]] = None) -> PostOut:
    usernames = username_lookup or {}
    return PostOut(
        id=post.id,
        thread_id=post.thread_id,
        user_id=post.user_id,
        username=usernames.get(str(post.user_id), str(post.user_id)),
        message=post.message,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


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


@router.get("/threads", response_model=List[ThreadOut])
def list_threads(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    threads = db.query(Thread).order_by(Thread.updated_at.desc()).all()
    username_lookup = _resolve_usernames(db, [str(thread.created_by) for thread in threads])
    return [_to_thread_out(thread, username_lookup) for thread in threads]


@router.post("/threads", response_model=ThreadOut, status_code=status.HTTP_201_CREATED)
def create_thread(
    body: ThreadCreate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    participants = [current_user.id]
    thread = Thread(
        category=body.category.strip(),
        title=body.title.strip(),
        created_by=current_user.id,
        message_count=0,
        participating_users=participants,
    )
    db.add(thread)
    db.flush()

    if body.initial_message and body.initial_message.strip():
        post = Post(
            thread_id=thread.id,
            user_id=current_user.id,
            message=body.initial_message.strip(),
        )
        db.add(post)
        thread.message_count = 1

    db.commit()
    db.refresh(thread)
    return _to_thread_out(thread, {str(current_user.id): current_user.username})


@router.get("/threads/{thread_id}", response_model=ThreadDetailOut)
def get_thread(
    thread_id: int,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    posts = (
        db.query(Post)
        .filter(Post.thread_id == thread.id)
        .order_by(Post.created_at.asc())
        .all()
    )
    user_ids = [str(thread.created_by), *[str(post.user_id) for post in posts]]
    username_lookup = _resolve_usernames(db, user_ids)
    return ThreadDetailOut(
        **_to_thread_out(thread, username_lookup).model_dump(),
        posts=[_to_post_out(post, username_lookup) for post in posts],
    )


@router.put("/threads/{thread_id}", response_model=ThreadOut)
def update_thread(
    thread_id: int,
    body: ThreadUpdate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if thread.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to update this thread")

    if body.category is not None:
        thread.category = body.category.strip()
    if body.title is not None:
        thread.title = body.title.strip()

    db.commit()
    db.refresh(thread)
    username_lookup = _resolve_usernames(db, [str(thread.created_by)])
    return _to_thread_out(thread, username_lookup)


@router.post("/threads/{thread_id}/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    thread_id: int,
    body: PostCreate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    post = Post(thread_id=thread.id, user_id=current_user.id, message=body.message.strip())
    db.add(post)

    participants = _normalize_participants(thread.participating_users)
    if current_user.id not in participants:
        participants.append(current_user.id)
    thread.participating_users = participants
    thread.message_count = thread.message_count + 1

    db.commit()
    db.refresh(post)
    return _to_post_out(post, {str(current_user.id): current_user.username})


@router.get("/threads/{thread_id}/posts", response_model=List[PostOut])
def list_posts(
    thread_id: int,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    posts = (
        db.query(Post)
        .filter(Post.thread_id == thread.id)
        .order_by(Post.created_at.asc())
        .all()
    )
    username_lookup = _resolve_usernames(db, [str(post.user_id) for post in posts])
    return [_to_post_out(post, username_lookup) for post in posts]


@router.put("/posts/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    body: PostUpdate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to update this post")

    post.message = body.message.strip()
    db.commit()
    db.refresh(post)
    return _to_post_out(post, {str(current_user.id): current_user.username})


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(
    thread_id: int,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if thread.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this thread")

    db.delete(thread)
    db.commit()


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this post")

    thread = db.query(Thread).filter(Thread.id == post.thread_id).first()
    db.delete(post)
    if thread:
        db.flush()
        _refresh_thread_stats(db, thread)
    db.commit()
