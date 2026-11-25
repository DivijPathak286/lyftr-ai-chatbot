import os
import sys
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

os.environ.setdefault("LLM_API_KEYS", "test-key-one,test-key-two")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/lyftr-test.db")
os.environ.setdefault("ENABLE_FAILURE_SIMULATION", "true")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app

def test_health_contract():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["keys_configured"] >= 2
        assert response.json()["cache_enabled"] is True

def test_unknown_session():
    with TestClient(app) as client:
        response = client.get("/sessions/does-not-exist/messages")
        assert response.status_code == 404
        assert response.json()["detail"] == "session not found"

def test_failure_simulation_all_keys():
    with TestClient(app) as client:
        response = client.post(
            "/chat",
            headers={"X-Simulate-Failure": "*=429"},
            json={"session_id": "all-fail-test", "message": "unique test prompt"}
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "all providers unavailable"}
        history = client.get("/sessions/all-fail-test/messages")
        assert history.status_code == 404
