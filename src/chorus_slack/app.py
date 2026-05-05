"""Minimal FastAPI skeleton for the Slack assistant.

Phase 2 scaffold: signature verification + URL verification handshake. No
event routing, no Bolt, no agent integration yet — those land in follow-up
PRs. Factory pattern (``create_app``) keeps the app testable without a
module-level singleton.
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from chorus_slack.signature import verify_slack_signature


def create_app() -> FastAPI:
    app = FastAPI(title="chorus-slack", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/slack/events")
    async def slack_events(request: Request) -> Response:
        signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        body = await request.body()

        if not verify_slack_signature(signing_secret, timestamp, body, signature):
            raise HTTPException(status_code=401, detail="invalid signature")

        try:
            payload: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError:
            return Response(status_code=200)

        if payload.get("type") == "url_verification":
            challenge = payload.get("challenge", "")
            return JSONResponse({"challenge": challenge})

        return Response(status_code=200)

    return app
