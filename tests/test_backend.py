import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.discussion import Post, Thread
from app.models.portfolio import Holding
from app.models.report import Report
from app.models.saved_news import SavedNews
from app.models.user import Profile
from app.models.watchlist import WatchlistItem
from app.routes.auth import _delete_user_local_data


@pytest.fixture(scope="session", autouse=True)
def ensure_tables_exist():
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_app_uses_real_database_settings():
    with engine.connect() as connection:
        assert connection.execute(text("select 1")).scalar_one() == 1


def test_root_endpoint_returns_ok(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_market_status_endpoint_returns_expected_shape(client):
    response = client.get("/stocks/status")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert "status" in payload
    assert isinstance(payload["status"], str)


def test_heatmap_endpoint_returns_list_shape(client):
    response = client.get("/api/heatmap")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    if payload:
        first = payload[0]
        assert isinstance(first, dict)
        assert "stock" in first
        assert "sector" in first
        assert "mcap" in first
        assert "change" in first


def test_stock_quote_endpoint_returns_expected_shape(client):
    response = client.get("/stocks/quote/AAPL")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert payload.get("symbol") == "AAPL"
    for field in ["name", "price", "change", "changePercent", "volume"]:
        assert field in payload


def test_stock_search_endpoint_returns_list_shape(client):
    response = client.get("/stocks/search", params={"q": "apple"})

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    if payload:
        first = payload[0]
        assert isinstance(first, dict)
        assert "symbol" in first
        assert "name" in first


def test_market_news_endpoint_returns_expected_shape(client):
    if not settings.FINNHUB_API_KEY or settings.FINNHUB_API_KEY.startswith("your-"):
        pytest.skip("FINNHUB_API_KEY is not configured for correctness test")

    response = client.get("/stocks/news", params={"category": "general"})

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)


@pytest.mark.parametrize(
    "path",
    [
        "/insights/technology",
        "/insights/financial",
    ],
)
def test_ai_sentiment_endpoints_return_list_shape(client, path):
    if not settings.HF_TOKEN or settings.HF_TOKEN.startswith("your-"):
        pytest.skip("HF_TOKEN is not configured for correctness test")

    response = client.get(path)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)


def test_ai_alerts_endpoint_returns_expected_shape(client):
    if not settings.HF_TOKEN or settings.HF_TOKEN.startswith("your-"):
        pytest.skip("HF_TOKEN is not configured for correctness test")

    response = client.get("/insights/alerts/")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    for field in ["ai_alert_1", "ai_alert_2", "ai_alert_3", "ai_alert_4"]:
        assert field in payload


def test_community_threads_endpoint_with_auth(client, auth_headers):
    response = client.get("/discussions/threads", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)


def test_portfolio_endpoints_with_auth(client, auth_headers):
    holdings_response = client.get("/portfolio/", headers=auth_headers)
    history_response = client.get("/portfolio/history", headers=auth_headers)

    assert holdings_response.status_code == 200
    assert history_response.status_code == 200
    assert isinstance(holdings_response.json(), list)
    assert isinstance(history_response.json(), list)


def test_delete_user_local_data_removes_related_rows_and_refreshes_thread_stats(db_session):
    user_id = f"test-user-{uuid.uuid4()}"
    other_user_id = f"test-user-{uuid.uuid4()}"
    thread_title = f"AAPL thoughts {uuid.uuid4().hex[:8]}"
    user_username = f"alice-{uuid.uuid4().hex[:8]}"
    other_username = f"bob-{uuid.uuid4().hex[:8]}"
    user_email = f"{user_username}@example.com"
    other_email = f"{other_username}@example.com"

    user = Profile(id=user_id, username=user_username, email=user_email, role="user")
    other_user = Profile(id=other_user_id, username=other_username, email=other_email, role="user")
    db_session.add_all([user, other_user])
    db_session.commit()

    thread = Thread(
        category="stocks",
        title=thread_title,
        created_by=other_user_id,
        message_count=2,
        participating_users=[user_id, other_user_id],
    )
    db_session.add(thread)
    db_session.commit()

    db_session.add_all([
        Post(thread_id=thread.id, user_id=user.id, message="first"),
        Post(thread_id=thread.id, user_id=other_user.id, message="second"),
        Holding(user_id=user.id, symbol="AAPL", quantity=2, purchase_price=100),
        WatchlistItem(user_id=user.id, symbol="MSFT"),
        SavedNews(
            user_id=user.id,
            external_id=1,
            headline="headline",
            source="source",
            url="https://example.com",
            published_at=1,
        ),
        Report(target_type="post", target_id=1, reason="spam", reported_by=user.id),
    ])
    db_session.commit()

    try:
        _delete_user_local_data(db_session, user.id)
        db_session.commit()

        remaining_thread = db_session.query(Thread).filter(Thread.id == thread.id).one()
        assert remaining_thread.message_count == 1
        assert remaining_thread.participating_users == [other_user_id]
        assert db_session.query(Profile).filter(Profile.id == user_id).first() is None
        assert db_session.query(Holding).filter(Holding.user_id == user_id).count() == 0
        assert db_session.query(WatchlistItem).filter(WatchlistItem.user_id == user_id).count() == 0
        assert db_session.query(SavedNews).filter(SavedNews.user_id == user_id).count() == 0
        assert db_session.query(Report).filter(Report.reported_by == user_id).count() == 0
        assert db_session.query(Post).filter(Post.user_id == user_id).count() == 0
    finally:
        db_session.query(Holding).filter(Holding.user_id.in_([user_id, other_user_id])).delete(synchronize_session=False)
        db_session.query(WatchlistItem).filter(WatchlistItem.user_id.in_([user_id, other_user_id])).delete(synchronize_session=False)
        db_session.query(SavedNews).filter(SavedNews.user_id.in_([user_id, other_user_id])).delete(synchronize_session=False)
        db_session.query(Report).filter(Report.reported_by.in_([user_id, other_user_id])).delete(synchronize_session=False)
        db_session.query(Post).filter(Post.thread_id == thread.id).delete(synchronize_session=False)
        db_session.query(Thread).filter(Thread.id == thread.id).delete(synchronize_session=False)
        db_session.query(Profile).filter(Profile.id.in_([user_id, other_user_id])).delete(synchronize_session=False)
        db_session.commit()