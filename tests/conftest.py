from pathlib import Path
import os
import uuid

from dotenv import load_dotenv
import pytest
from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)


@pytest.fixture(scope="session")
def test_bearer_token():
	token = os.getenv("TEST_BEARER_TOKEN", "").strip()
	if token:
		return token

	username = f"pytest_{uuid.uuid4().hex[:10]}"
	email = f"{username}@example.com"
	password = f"Pyt3st!{uuid.uuid4().hex[:10]}"

	with TestClient(app) as client:
		response = client.post(
			"/auth/register",
			json={
				"username": username,
				"email": email,
				"password": password,
			},
		)

	if response.status_code != 200:
		pytest.fail(
			"Could not auto-create test bearer token via /auth/register. "
			f"Status: {response.status_code}, Body: {response.text}"
		)

	token = response.json().get("access_token", "").strip()
	if not token:
		pytest.fail("/auth/register succeeded but did not return access_token")

	os.environ["TEST_BEARER_TOKEN"] = token
	return token


@pytest.fixture()
def auth_headers(test_bearer_token):
	return {"Authorization": f"Bearer {test_bearer_token}"}
