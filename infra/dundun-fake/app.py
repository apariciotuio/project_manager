"""Dundun fake HTTP service (EP-21 F-6).

Mimics the Dundun POST /messages contract for local dev and E2E testing.
Stateless — in-memory only, wiped on restart.

Environment variables:
    FAKE_MODE   deterministic (default) | stochastic
                - deterministic: 100ms fixed delay, canned echo response
                - stochastic:    300-800ms random delay, templated responses

Request headers:
    X-Fake-Force-Error: 500  → returns 500 FAKE_FORCED
    X-Fake-Force-Error: 429  → returns 429 with Retry-After: 2
"""
from __future__ import annotations

import asyncio
import os
import random
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

FAKE_MODE = os.getenv("FAKE_MODE", "deterministic")

_CANNED_RESPONSES = [
    "I've processed your request. Here is a summary of the work item.",
    "Based on the description, the acceptance criteria look well-defined.",
    "I suggest clarifying the edge cases before moving to implementation.",
    "The task seems ready for development. Shall I generate sub-tasks?",
    "I've reviewed the requirements. A few open questions remain.",
]

app = FastAPI(title="dundun-fake", version="0.1.0")


class MessageRequest(BaseModel):
    thread_id: str
    content: str
    user_id: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/messages")
async def post_message(
    body: MessageRequest,
    x_fake_force_error: str | None = Header(default=None),
) -> Any:
    # Error injection via header
    if x_fake_force_error == "500":
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "FAKE_FORCED", "message": "forced error by header"}},
        )
    if x_fake_force_error == "429":
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "RATE_LIMITED", "message": "rate limit simulated"}},
            headers={"Retry-After": "2"},
        )

    # Simulate latency
    if FAKE_MODE == "stochastic":
        delay = random.uniform(0.3, 0.8)  # noqa: S311
        response_content = random.choice(_CANNED_RESPONSES)  # noqa: S311
    else:
        delay = 0.1
        response_content = f"[echo] {body.content}"

    await asyncio.sleep(delay)

    return {
        "message_id": str(uuid4()),
        "thread_id": body.thread_id,
        "role": "assistant",
        "content": response_content,
        "created_at": datetime.now(UTC).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)  # noqa: S104
