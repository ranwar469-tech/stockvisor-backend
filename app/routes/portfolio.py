"""Portfolio routes — CRUD for user holdings with live price enrichment."""

from typing import List

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.portfolio import Holding
from app.models.portfolio_activity import PortfolioActivity
from app.models.user import Profile
from app.schemas.portfolio import HoldingCreate, HoldingResponse, HoldingSell, PortfolioActivityOut

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _to_activity_out(activity: PortfolioActivity) -> PortfolioActivityOut:
    return PortfolioActivityOut(
        id=activity.id,
        activityType=activity.activity_type,
        symbol=activity.symbol,
        name=activity.name,
        shares=activity.shares,
        price=activity.price,
        createdAt=activity.created_at,
    )


def _seed_history_from_current_holdings(db: Session, user_id: str) -> None:
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    if not holdings:
        return

    existing_seed_ids = {
        seeded_id
        for (seeded_id,) in (
            db.query(PortfolioActivity.seeded_from_holding_id)
            .filter(
                PortfolioActivity.user_id == user_id,
                PortfolioActivity.activity_type == "buy",
                PortfolioActivity.seeded_from_holding_id.isnot(None),
            )
            .all()
        )
        if seeded_id is not None
    }

    for holding in holdings:
        if holding.id in existing_seed_ids:
            continue
        db.add(
            PortfolioActivity(
                user_id=user_id,
                symbol=holding.symbol,
                name=holding.name,
                activity_type="buy",
                shares=holding.quantity,
                price=holding.purchase_price,
                seeded_from_holding_id=holding.id,
                created_at=holding.created_at,
            )
        )

    db.commit()


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
        "sector": holding.sector,
        "quantity": holding.quantity,
        "purchasePrice": holding.purchase_price,
        "currentPrice": round(price, 2),
        "dailyChange": change,
        "dailyChangePercent": change_pct,
        "createdAt": holding.created_at,
    }


@router.get("/", response_model=List[HoldingResponse])
def list_holdings(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all holdings for the current user, enriched with live prices."""
    holdings = db.query(Holding).filter(Holding.user_id == current_user.id).all()
    return [_enrich(h) for h in holdings]


@router.get("/history", response_model=List[PortfolioActivityOut])
def list_portfolio_history(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return persistent buy/sell history for current user."""
    _seed_history_from_current_holdings(db, current_user.id)
    activities = (
        db.query(PortfolioActivity)
        .filter(PortfolioActivity.user_id == current_user.id)
        .order_by(PortfolioActivity.created_at.desc(), PortfolioActivity.id.desc())
        .all()
    )
    return [_to_activity_out(activity) for activity in activities]


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

        db.add(
            PortfolioActivity(
                user_id=current_user.id,
                symbol=symbol,
                name=existing.name,
                activity_type="buy",
                shares=body.quantity,
                price=body.purchase_price,
            )
        )

        db.commit()
        db.refresh(existing)
        return _enrich(existing)

    # Try to resolve the company name and sector via yfinance
    try:
        info = yf.Ticker(symbol).get_info() or {}
        name = info.get("shortName") or info.get("longName") or symbol
        sector = info.get("sector")
    except Exception:
        name = symbol
        sector = None

    holding = Holding(
        user_id=current_user.id,
        symbol=symbol,
        name=name,
        sector=sector,
        quantity=body.quantity,
        purchase_price=body.purchase_price,
    )
    db.add(holding)
    db.flush()
    db.add(
        PortfolioActivity(
            user_id=current_user.id,
            symbol=symbol,
            name=name,
            activity_type="buy",
            shares=body.quantity,
            price=body.purchase_price,
            seeded_from_holding_id=holding.id,
            created_at=holding.created_at,
        )
    )
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
    db.add(
        PortfolioActivity(
            user_id=current_user.id,
            symbol=holding.symbol,
            name=holding.name,
            activity_type="sell",
            shares=body.quantity,
            price=holding.purchase_price,
        )
    )
    if remaining_quantity <= 0:
        sold_snapshot = {
            "id": holding.id,
            "symbol": holding.symbol,
            "name": holding.name or holding.symbol,
            "sector": holding.sector,
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
