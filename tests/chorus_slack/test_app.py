from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from chorus_slack.app import create_app

SECRET = "test-signing-secret"


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    base = b"v0:" + timestamp.encode("ascii") + b":" + body
    return "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SECRET)
    return TestClient(create_app())


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_url_verification_with_valid_signature(client: TestClient) -> None:
    ts = str(int(time.time()))
    body = json.dumps({"type": "url_verification", "challenge": "abc123"}).encode("utf-8")
    sig = _sign(SECRET, ts, body)

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    assert resp.json() == {"challenge": "abc123"}


def test_bad_signature_returns_401(client: TestClient) -> None:
    ts = str(int(time.time()))
    body = b'{"type":"url_verification","challenge":"x"}'

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": "v0=" + "0" * 64,
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 401


def test_stale_timestamp_returns_401(client: TestClient) -> None:
    ts = str(int(time.time()) - 3600)
    body = b'{"type":"url_verification","challenge":"x"}'
    sig = _sign(SECRET, ts, body)

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 401


def test_unknown_event_type_returns_200_empty(client: TestClient) -> None:
    ts = str(int(time.time()))
    body = json.dumps({"type": "event_callback", "event": {"type": "message"}}).encode("utf-8")
    sig = _sign(SECRET, ts, body)

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    assert resp.content == b""
