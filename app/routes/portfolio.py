"""Portfolio routes — CRUD for user holdings with live price enrichment."""

from typing import List

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.portfolio import Holding
from app.models.user import Profile
from app.schemas.portfolio import HoldingCreate, HoldingResponse, HoldingSell

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _enrich(holding: Holding) -> dict:
    """Fetch live price for a holding and return a dict matching HoldingResponse."""
    try:
        ticker = yf.Ticker(holding.symbol)
        info = ticker.info or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice") or holding.purchase_price
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose") or price
        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0
        name = info.get("shortName") or info.get("longName") or holding.name or holding.symbol
    except Exception:
        price = holding.purchase_price
        change = 0.0
        change_pct = 0.0
        name = holding.name or holding.symbol

    return {
        "id": holding.id,
        "symbol": holding.symbol,
        "name": name,
        "quantity": holding.quantity,
        "purchasePrice": holding.purchase_price,
        "currentPrice": round(price, 2),
        "dailyChange": change,
        "dailyChangePercent": change_pct,
    }


@router.get("/", response_model=List[HoldingResponse])
def list_holdings(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all holdings for the current user, enriched with live prices."""
    holdings = db.query(Holding).filter(Holding.user_id == current_user.id).all()
    return [_enrich(h) for h in holdings]


@router.post("/", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
def add_holding(
    body: HoldingCreate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a holding or merge it into an existing symbol for the current user."""
    symbol = body.symbol.upper().strip()

    existing = (
        db.query(Holding)
        .filter(Holding.user_id == current_user.id, Holding.symbol == symbol)
        .first()
    )
    if existing:
        total_quantity = existing.quantity + body.quantity
        total_cost = (existing.quantity * existing.purchase_price) + (
            body.quantity * body.purchase_price
        )

        existing.quantity = total_quantity
        existing.purchase_price = total_cost / total_quantity if total_quantity else 0.0

        db.commit()
        db.refresh(existing)
        return _enrich(existing)

    # Try to resolve the company name via yfinance
    try:
        info = yf.Ticker(symbol).info or {}
        name = info.get("shortName") or info.get("longName") or symbol
    except Exception:
        name = symbol

    holding = Holding(
        user_id=current_user.id,
        symbol=symbol,
        name=name,
        quantity=body.quantity,
        purchase_price=body.purchase_price,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)

    return _enrich(holding)


@router.post("/sell", response_model=HoldingResponse)
def sell_holding(
    body: HoldingSell,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sell shares from an existing holding for the current user."""
    symbol = body.symbol.upper().strip()

    if body.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be greater than 0",
        )

    holding = (
        db.query(Holding)
        .filter(Holding.user_id == current_user.id, Holding.symbol == symbol)
        .first()
    )
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    if body.quantity > holding.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sell quantity exceeds owned quantity",
        )

    remaining_quantity = holding.quantity - body.quantity
    if remaining_quantity <= 0:
        sold_snapshot = {
            "id": holding.id,
            "symbol": holding.symbol,
            "name": holding.name or holding.symbol,
            "quantity": 0.0,
            "purchasePrice": holding.purchase_price,
            "currentPrice": holding.purchase_price,
            "dailyChange": 0.0,
            "dailyChangePercent": 0.0,
        }
        db.delete(holding)
        db.commit()
        return sold_snapshot

    holding.quantity = remaining_quantity
    db.commit()
    db.refresh(holding)
    return _enrich(holding)


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_holding(
    holding_id: int,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a holding by ID. Only the owner can delete it."""
    holding = (
        db.query(Holding)
        .filter(Holding.id == holding_id, Holding.user_id == current_user.id)
        .first()
    )
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    db.delete(holding)
    db.commit()
