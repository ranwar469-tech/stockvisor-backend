"""Watchlist routes — manage user's watched stock symbols."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.watchlist import WatchlistItem
from app.models.user import Profile

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


# ---------- Schemas (kept local — lightweight) ---------- #

class WatchlistAdd(BaseModel):
    symbol: str


class WatchlistOut(BaseModel):
    id: int
    symbol: str

    class Config:
        from_attributes = True


# ---------- Endpoints ---------- #

@router.get("/", response_model=List[WatchlistOut])
def list_watchlist(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all watchlist symbols for the current user."""
    items = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == current_user.id)
        .order_by(WatchlistItem.added_at.desc())
        .all()
    )
    return items


@router.post("/", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    body: WatchlistAdd,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a symbol to the user's watchlist. 409 if already present."""
    symbol = body.symbol.upper().strip()

    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == current_user.id, WatchlistItem.symbol == symbol)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{symbol} is already in your watchlist.",
        )

    item = WatchlistItem(user_id=current_user.id, symbol=symbol)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_watchlist(
    symbol: str,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a symbol from the user's watchlist."""
    symbol = symbol.upper().strip()
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == current_user.id, WatchlistItem.symbol == symbol)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Symbol not in watchlist")
    db.delete(item)
    db.commit()
