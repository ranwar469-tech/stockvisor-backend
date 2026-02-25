import math
from typing import List, Dict

from fastapi import APIRouter
import yfinance as yf

router = APIRouter(prefix="/api")

# Define the sectors and their representative stocks
MARKET_SECTORS: Dict[str, List[str]] = {
    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "ORCL", "ADBE"],
    "Financial": ["JPM", "BAC", "GS", "MS", "WFC", "V"],
    "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "TMO"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC"]
}


@router.get("/heatmap")
def get_heatmap_data():
    """Return a list of heatmap data for frontend consumption.

    Each item contains: `stock`, `sector`, `mcap`, and `change` (percentage).
    """
    all_symbols = [ticker for sublist in MARKET_SECTORS.values() for ticker in sublist]

    # Fetch recent data in bulk to calculate % change efficiently
    data = yf.download(all_symbols, period="2d", group_by='ticker', progress=False)

    heatmap_results = []

    for sector_name, tickers in MARKET_SECTORS.items():
        for symbol in tickers:
            try:
                ticker_data = data.get(symbol)
                if ticker_data is not None and len(ticker_data) >= 2:
                    close_today = ticker_data['Close'].iloc[-1]
                    close_yesterday = ticker_data['Close'].iloc[-2]
                    change_pct = ((close_today - close_yesterday) / close_yesterday) * 100
                else:
                    change_pct = 0.0

                # Fetch market cap (consider caching in production)
                ticker_info = yf.Ticker(symbol).info
                market_cap = ticker_info.get("marketCap", 0)

                change_val = round(float(change_pct), 2)
                heatmap_results.append({
                    "stock": symbol,
                    "sector": sector_name,
                    "mcap": market_cap,
                    "change": 0.0 if math.isnan(change_val) else change_val
                })
            except Exception:
                # Skip symbols with errors; keep endpoint resilient
                continue

    return heatmap_results
