import os
import uuid

from locust import HttpUser, TaskSet, between, task


class ApiLoadTasks(TaskSet):
    def on_start(self):
        self._token = self._resolve_or_create_token()

    def _resolve_or_create_token(self):
        token = os.getenv("LOCUST_BEARER_TOKEN", "").strip() or os.getenv("TEST_BEARER_TOKEN", "").strip()
        if token:
            return token

        username = f"locust_{uuid.uuid4().hex[:10]}"
        email = f"{username}@example.com"
        password = f"Locust!{uuid.uuid4().hex[:10]}"

        response = self.client.post(
            "/auth/register",
            json={
                "username": username,
                "email": email,
                "password": password,
            },
            name="/auth/register",
        )

        if response.status_code != 200:
            return ""

        payload = response.json() if response.content else {}
        return (payload.get("access_token") or "").strip()

    def _auth_headers(self):
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    def _extract_first_thread_id(self):
        headers = self._auth_headers()
        with self.client.get("/discussions/threads", headers=headers, name="/discussions/threads", catch_response=True) as response:
            if response.status_code != 200:
                response.success()
                return None
            try:
                payload = response.json()
            except Exception:
                return None
            if isinstance(payload, list) and payload:
                first = payload[0]
                if isinstance(first, dict):
                    return first.get("id")
            return None

    @task(3)
    def root(self):
        self.client.get("/")

    @task(3)
    def market_status(self):
        self.client.get("/stocks/status")

    @task(2)
    def heatmap(self):
        self.client.get("/api/heatmap")

    @task(2)
    def stock_price(self):
        self.client.get("/stocks/quote/AAPL")

    @task(2)
    def expert_analysis_chart(self):
        self.client.get("/stocks/recommendations?symbol=AAPL")

    @task(2)
    def market_news(self):
        self.client.get("/stocks/news?category=general")

    @task(2)
    def news(self):
        self.client.get("/stocks/news?category=general")

    @task(1)
    def ai_sentiment_technology(self):
        self.client.get("/insights/technology")

    @task(1)
    def ai_sentiment_financial(self):
        self.client.get("/insights/financial")

    @task(1)
    def ai_insight_alerts(self):
        self.client.get("/insights/alerts/")

    @task(2)
    def community_threads(self):
        self.client.get("/discussions/threads", headers=self._auth_headers())

    @task(1)
    def community_thread_details(self):
        thread_id = self._extract_first_thread_id()
        if thread_id is None:
            return
        headers = self._auth_headers()
        self.client.get(f"/discussions/threads/{thread_id}", headers=headers, name="/discussions/threads/{thread_id}")
        self.client.get(f"/discussions/threads/{thread_id}/posts", headers=headers, name="/discussions/threads/{thread_id}/posts")

    @task(2)
    def portfolio_holdings(self):
        self.client.get("/portfolio/", headers=self._auth_headers())

    @task(1)
    def portfolio_history(self):
        self.client.get("/portfolio/history", headers=self._auth_headers())


class StockvisorLoadTestUser(HttpUser):
    host = os.getenv("LOCUST_HOST", os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    wait_time = between(1, 3)
    tasks = [ApiLoadTasks]