"""FastAPI endpoint smoke tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import anthropic
from fastapi.testclient import TestClient

import src.api.main as _main_module
from src.api.main import app

# Unit tests don't start the FastAPI lifespan (TestClient is not used as a context
# manager), so _INDEX_READY is never set via the warm-up thread.
# Pre-set it here so /chat tests exercise the happy path.
# The warm-up 503 path is tested explicitly in test_warmup_pending_returns_503.
_main_module._INDEX_READY.set()


def _mock_response() -> MagicMock:
    """Minimal httpx.Response mock satisfying the Anthropic exception constructor."""
    resp = MagicMock()
    resp.request = MagicMock()
    return resp

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_ok(self) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        # Readiness fields: surface config state without an API call.
        assert "model" in body
        assert "key_configured" in body
        assert isinstance(body["key_configured"], bool)
        # index_ready must always be present in /health.
        assert "index_ready" in body
        assert isinstance(body["index_ready"], bool)


class TestChatEndpoint:
    def test_valid_query_returns_200(self) -> None:
        mock_result = {
            "answer": "Here is the answer.",
            "tools_called": ["search_process_docs"],
            "turns": 2,
        }
        with patch("src.api.main.run_agent_async", return_value=mock_result):
            resp = client.post("/chat", json={"query": "How do I request PTO?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Here is the answer."
        assert data["tools_called"] == ["search_process_docs"]
        assert data["turns"] == 2

    def test_empty_query_returns_400(self) -> None:
        resp = client.post("/chat", json={"query": "   "})
        assert resp.status_code == 400

    def test_missing_query_field_returns_422(self) -> None:
        resp = client.post("/chat", json={})
        assert resp.status_code == 422

    def test_response_schema_complete(self) -> None:
        mock_result = {
            "answer": "Answer.",
            "tools_called": [],
            "turns": 1,
        }
        with patch("src.api.main.run_agent_async", return_value=mock_result):
            resp = client.post("/chat", json={"query": "test"})
        data = resp.json()
        assert "answer" in data
        assert "tools_called" in data
        assert "turns" in data

    def test_auth_error_returns_503(self) -> None:
        with patch(
            "src.api.main.run_agent_async",
            side_effect=anthropic.AuthenticationError(
                message="invalid key", response=_mock_response(), body=None
            ),
        ):
            resp = client.post("/chat", json={"query": "test"})
        assert resp.status_code == 503
        assert "API key" in resp.json()["detail"]

    def test_connection_error_returns_503(self) -> None:
        with patch(
            "src.api.main.run_agent_async",
            side_effect=anthropic.APIConnectionError(request=_mock_response().request),
        ):
            resp = client.post("/chat", json={"query": "test"})
        assert resp.status_code == 503
        assert "connect" in resp.json()["detail"].lower()

    def test_rate_limit_error_returns_429(self) -> None:
        with patch(
            "src.api.main.run_agent_async",
            side_effect=anthropic.RateLimitError(
                message="rate limit", response=_mock_response(), body=None
            ),
        ):
            resp = client.post("/chat", json={"query": "test"})
        assert resp.status_code == 429
        assert "rate limit" in resp.json()["detail"].lower()

    def test_overloaded_error_returns_503(self) -> None:
        with patch(
            "src.api.main.run_agent_async",
            side_effect=anthropic.InternalServerError(
                message="overloaded", response=_mock_response(), body=None
            ),
        ):
            resp = client.post("/chat", json={"query": "test"})
        assert resp.status_code == 503
        assert "overloaded" in resp.json()["detail"].lower()

    def test_generic_exception_returns_500(self) -> None:
        with patch(
            "src.api.main.run_agent_async",
            side_effect=RuntimeError("unexpected"),
        ):
            resp = client.post("/chat", json={"query": "test"})
        assert resp.status_code == 500

    def test_warmup_pending_returns_503(self) -> None:
        """While _INDEX_READY is unset, /chat must return 503 with a retry hint."""
        _main_module._INDEX_READY.clear()
        try:
            resp = client.post("/chat", json={"query": "How do I request PTO?"})
            assert resp.status_code == 503
            detail = resp.json()["detail"]
            assert "warming up" in detail.lower()
            assert "30" in detail  # retry hint present
        finally:
            _main_module._INDEX_READY.set()  # restore for subsequent tests
