"""Models package — re-export all models so Base.metadata discovers them."""

from app.models.user import Profile  # noqa: F401
from app.models.portfolio import Holding  # noqa: F401
from app.models.watchlist import WatchlistItem  # noqa: F401
