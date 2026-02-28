"""Pydantic schemas for discussions endpoints."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ThreadCreate(BaseModel):
    category: str
    title: str
    initial_message: Optional[str] = None


class ThreadUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None


class PostCreate(BaseModel):
    message: str


class PostUpdate(BaseModel):
    message: str


class PostOut(BaseModel):
    id: int
    thread_id: int
    user_id: str
    username: str
    message: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ThreadOut(BaseModel):
    id: int
    category: str
    title: str
    created_by: str
    created_by_username: str
    message_count: int
    participating_users: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ThreadDetailOut(ThreadOut):
    posts: List[PostOut]
