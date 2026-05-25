import uuid

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.portfolio_activity import PortfolioActivity
from app.models.report import Report
import pytest


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_discussions_thread_post_crud_flow(client, auth_headers):
    thread_id = None
    post_id = None
    try:
        create_thread_response = client.post(
            "/discussions/threads",
            headers=auth_headers,
            json={
                "category": "stocks",
                "title": f"Pytest thread {uuid.uuid4().hex[:8]}",
                "initial_message": "Initial message from pytest",
            },
        )
        assert create_thread_response.status_code == 201
        created_thread = create_thread_response.json()
        thread_id = created_thread["id"]

        get_thread_response = client.get(f"/discussions/threads/{thread_id}", headers=auth_headers)
        assert get_thread_response.status_code == 200
        thread_payload = get_thread_response.json()
        assert thread_payload["id"] == thread_id
        assert isinstance(thread_payload.get("posts"), list)
        if thread_payload["posts"]:
            post_id = thread_payload["posts"][0]["id"]

        create_post_response = client.post(
            f"/discussions/threads/{thread_id}/posts",
            headers=auth_headers,
            json={"message": "Second message from pytest"},
        )
        assert create_post_response.status_code == 201
        created_post = create_post_response.json()
        post_id = created_post["id"]

        update_post_response = client.put(
            f"/discussions/posts/{post_id}",
            headers=auth_headers,
            json={"message": "Updated pytest post"},
        )
        assert update_post_response.status_code == 200
        assert update_post_response.json()["message"] == "Updated pytest post"

        report_post_response = client.post(
            f"/discussions/posts/{post_id}/reports",
            headers=auth_headers,
            json={"reason": "pytest correctness flow"},
        )
        assert report_post_response.status_code == 201
        assert report_post_response.json()["target_type"] == "post"

        report_thread_response = client.post(
            f"/discussions/threads/{thread_id}/reports",
            headers=auth_headers,
            json={"reason": "pytest thread report flow"},
        )
        assert report_thread_response.status_code == 201
        assert report_thread_response.json()["target_type"] == "thread"

        list_posts_response = client.get(f"/discussions/threads/{thread_id}/posts", headers=auth_headers)
        assert list_posts_response.status_code == 200
        assert isinstance(list_posts_response.json(), list)
    finally:
        if post_id is not None:
            client.delete(f"/discussions/posts/{post_id}", headers=auth_headers)

        if thread_id is not None:
            client.delete(f"/discussions/threads/{thread_id}", headers=auth_headers)

        if thread_id is not None or post_id is not None:
            db = SessionLocal()
            try:
                if post_id is not None:
                    db.query(Report).filter(
                        Report.target_type == "post",
                        Report.target_id == post_id,
                    ).delete(synchronize_session=False)
                if thread_id is not None:
                    db.query(Report).filter(
                        Report.target_type == "thread",
                        Report.target_id == thread_id,
                    ).delete(synchronize_session=False)
                db.commit()
            finally:
                db.close()


def test_portfolio_holding_crud_flow(client, auth_headers):
    symbol = f"T{uuid.uuid4().hex[:4]}".upper()
    holding_id = None
    user_id = None

    try:
        me_response = client.get("/auth/me", headers=auth_headers)
        assert me_response.status_code == 200
        user_id = me_response.json()["id"]

        add_holding_response = client.post(
            "/portfolio/",
            headers=auth_headers,
            json={"symbol": symbol, "quantity": 3, "purchase_price": 100},
        )
        assert add_holding_response.status_code == 201
        holding_payload = add_holding_response.json()
        holding_id = holding_payload["id"]
        assert holding_payload["symbol"] == symbol

        list_holdings_response = client.get("/portfolio/", headers=auth_headers)
        assert list_holdings_response.status_code == 200
        assert isinstance(list_holdings_response.json(), list)

        history_response = client.get("/portfolio/history", headers=auth_headers)
        assert history_response.status_code == 200
        assert isinstance(history_response.json(), list)

        sell_response = client.post(
            "/portfolio/sell",
            headers=auth_headers,
            json={"symbol": symbol, "quantity": 1},
        )
        assert sell_response.status_code == 200
        sell_payload = sell_response.json()
        assert sell_payload["symbol"] == symbol
    finally:
        if holding_id is not None:
            client.delete(f"/portfolio/{holding_id}", headers=auth_headers)

        if user_id is not None:
            db = SessionLocal()
            try:
                db.query(PortfolioActivity).filter(
                    PortfolioActivity.user_id == user_id,
                    PortfolioActivity.symbol == symbol,
                ).delete(synchronize_session=False)
                db.commit()
            finally:
                db.close()
