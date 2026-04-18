"""Integration tests for the Dundun fake HTTP service (EP-21 F-6).

Uses FastAPI TestClient against the fake app directly — no Docker required.
The fake app lives at infra/dundun-fake/app.py; we import it by path to avoid
adding it to the main backend package.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Import infra/dundun-fake/app.py without adding it to the main package tree
# ---------------------------------------------------------------------------

_FAKE_APP_PATH = Path(__file__).parent.parent.parent.parent / "infra" / "dundun-fake" / "app.py"


def _load_fake_app() -> object:
    spec = importlib.util.spec_from_file_location("dundun_fake_app", _FAKE_APP_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dundun_fake_app"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_module = _load_fake_app()
_fake_fastapi_app = _module.app  # type: ignore[attr-defined]

client = TestClient(_fake_fastapi_app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_returns_200() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /messages — happy path
# ---------------------------------------------------------------------------


def test_post_messages_returns_assistant_message() -> None:
    payload = {"thread_id": "thread-1", "content": "hello world", "user_id": "user-42"}
    response = client.post("/messages", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == "thread-1"
    assert body["role"] == "assistant"
    assert "message_id" in body
    assert "content" in body
    assert "created_at" in body


def test_post_messages_deterministic_mode_echoes_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_module, "FAKE_MODE", "deterministic")
    payload = {"thread_id": "t-echo", "content": "my specific message", "user_id": "u-1"}
    response = client.post("/messages", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "my specific message" in body["content"]


def test_post_messages_message_id_is_unique() -> None:
    payload = {"thread_id": "t-1", "content": "ping", "user_id": "u-1"}
    r1 = client.post("/messages", json=payload)
    r2 = client.post("/messages", json=payload)
    assert r1.json()["message_id"] != r2.json()["message_id"]


# ---------------------------------------------------------------------------
# Error injection via X-Fake-Force-Error header
# ---------------------------------------------------------------------------


def test_force_error_500() -> None:
    response = client.post(
        "/messages",
        json={"thread_id": "t", "content": "x", "user_id": "u"},
        headers={"X-Fake-Force-Error": "500"},
    )
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "FAKE_FORCED"


def test_force_error_429_returns_retry_after() -> None:
    response = client.post(
        "/messages",
        json={"thread_id": "t", "content": "x", "user_id": "u"},
        headers={"X-Fake-Force-Error": "429"},
    )
    assert response.status_code == 429
    assert response.headers.get("retry-after") == "2"


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------


def test_missing_thread_id_returns_422() -> None:
    response = client.post("/messages", json={"content": "hi", "user_id": "u"})
    assert response.status_code == 422


def test_missing_content_returns_422() -> None:
    response = client.post("/messages", json={"thread_id": "t", "user_id": "u"})
    assert response.status_code == 422
