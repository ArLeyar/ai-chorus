"""Slack request signature verification.

Implements the v0 HMAC-SHA256 scheme documented at
https://api.slack.com/authentication/verifying-requests-from-slack.
"""

from __future__ import annotations

import hashlib
import hmac
import time


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
    *,
    max_age_seconds: int = 300,
    now: float | None = None,
) -> bool:
    if not signing_secret or not timestamp or not signature:
        return False

    if not signature.startswith("v0="):
        return False

    try:
        ts_int = int(timestamp)
    except ValueError:
        return False

    current = time.time() if now is None else now
    if abs(current - ts_int) > max_age_seconds:
        return False

    basestring = b"v0:" + timestamp.encode("ascii") + b":" + body
    expected = (
        "v0=" + hmac.new(signing_secret.encode("utf-8"), basestring, hashlib.sha256).hexdigest()
    )

    return hmac.compare_digest(expected, signature)
