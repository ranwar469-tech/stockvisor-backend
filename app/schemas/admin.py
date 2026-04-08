"""Pydantic schemas for admin management endpoints."""

from datetime import datetime

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    id: str
    username: str
    email: str
    role: str
    created_at: datetime | None = None
    banned_until: datetime | None = None

    class Config:
        from_attributes = True


class BanUserRequest(BaseModel):
    ban_duration: str = "876000h"


class AdminReportOut(BaseModel):
    id: int
    target_type: str
    target_id: int
    thread_id: int | None = None
    thread_title: str | None = None
    reason: str
    details: str | None = None
    reported_by: str
    reported_by_username: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True
