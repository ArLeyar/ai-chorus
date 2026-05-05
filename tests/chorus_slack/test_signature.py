from __future__ import annotations

import hashlib
import hmac

from chorus_slack.signature import verify_slack_signature

SECRET = "test-signing-secret"


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    base = b"v0:" + timestamp.encode("ascii") + b":" + body
    return "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()


def test_valid_signature_fresh_timestamp() -> None:
    now = 1_700_000_000.0
    ts = "1700000000"
    body = b'{"type":"event_callback"}'
    sig = _sign(SECRET, ts, body)

    assert verify_slack_signature(SECRET, ts, body, sig, now=now) is True


def test_tampered_body_returns_false() -> None:
    now = 1_700_000_000.0
    ts = "1700000000"
    body = b'{"type":"event_callback"}'
    sig = _sign(SECRET, ts, body)

    assert verify_slack_signature(SECRET, ts, b'{"type":"tampered"}', sig, now=now) is False


def test_wrong_signing_secret_returns_false() -> None:
    now = 1_700_000_000.0
    ts = "1700000000"
    body = b"hello"
    sig = _sign("other-secret", ts, body)

    assert verify_slack_signature(SECRET, ts, body, sig, now=now) is False


def test_stale_timestamp_returns_false() -> None:
    now = 1_700_000_000.0
    ts = "1699999000"
    body = b"hello"
    sig = _sign(SECRET, ts, body)

    assert verify_slack_signature(SECRET, ts, body, sig, now=now) is False


def test_future_timestamp_beyond_skew_returns_false() -> None:
    now = 1_700_000_000.0
    ts = "1700001000"
    body = b"hello"
    sig = _sign(SECRET, ts, body)

    assert verify_slack_signature(SECRET, ts, body, sig, now=now) is False


def test_malformed_signature_no_v0_prefix_returns_false() -> None:
    now = 1_700_000_000.0
    ts = "1700000000"
    body = b"hello"
    raw = _sign(SECRET, ts, body).removeprefix("v0=")

    assert verify_slack_signature(SECRET, ts, body, raw, now=now) is False


def test_mismatched_signature_returns_false() -> None:
    now = 1_700_000_000.0
    ts = "1700000000"
    body = b"hello"

    assert verify_slack_signature(SECRET, ts, body, "v0=" + "0" * 64, now=now) is False


def test_non_numeric_timestamp_returns_false() -> None:
    assert verify_slack_signature(SECRET, "not-a-number", b"x", "v0=abc", now=0.0) is False


def test_empty_secret_returns_false() -> None:
    assert verify_slack_signature("", "1700000000", b"x", "v0=abc", now=1_700_000_000.0) is False


def test_default_now_uses_real_clock() -> None:
    import time

    ts = str(int(time.time()))
    body = b"x"
    sig = _sign(SECRET, ts, body)
    assert verify_slack_signature(SECRET, ts, body, sig) is True
