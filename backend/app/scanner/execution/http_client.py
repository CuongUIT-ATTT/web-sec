"""Read-only HTTP execution with isolated bearer contexts and bounded observations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from backend.app.core.settings import Settings
from backend.app.domain.contracts import ExecutionStatus
from backend.app.scanner.execution.scope import TargetScopeError, build_request_url


@dataclass(frozen=True)
class HttpObservation:
    execution_status: ExecutionStatus
    status_code: int | None
    json_body: Any | None
    body_length: int
    body_truncated: bool
    parse_error: bool
    reason_codes: tuple[str, ...]


async def get_json(
    *,
    base_url: str,
    api_path: str,
    bearer_token: str | None,
    settings: Settings,
    timeout_seconds: float | None = None,
) -> HttpObservation:
    """Execute exactly one bounded GET without redirects or inherited cookies."""
    try:
        url = build_request_url(base_url, api_path, settings)
    except TargetScopeError:
        return HttpObservation(ExecutionStatus.SCOPE_BLOCKED, None, None, 0, False, False, ("execution.scope_blocked",))
    headers = {"Accept": "application/json"}
    if bearer_token is not None:
        headers["Authorization"] = f"Bearer {bearer_token}"
    timeout = timeout_seconds if timeout_seconds is not None else settings.default_timeout_seconds
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=timeout, cookies=None) as client:
            async with client.stream("GET", url, headers=headers) as response:
                chunks: list[bytes] = []
                body_length = 0
                truncated = False
                async for chunk in response.aiter_bytes():
                    remaining = settings.max_response_bytes - body_length
                    if remaining <= 0:
                        truncated = True
                        break
                    chunks.append(chunk[:remaining])
                    body_length += len(chunks[-1])
                    if len(chunk) > remaining:
                        truncated = True
                        break
                if truncated:
                    return HttpObservation(ExecutionStatus.BODY_TRUNCATED, response.status_code, None, body_length, True, False, ("evidence.body_truncated",))
                raw_body = b"".join(chunks)
                try:
                    json_body = json.loads(raw_body) if raw_body else None
                except json.JSONDecodeError:
                    return HttpObservation(ExecutionStatus.JSON_PARSE_ERROR, response.status_code, None, body_length, False, True, ("evidence.json_parse_error",))
                return HttpObservation(ExecutionStatus.COMPLETED_RESPONSE, response.status_code, json_body, body_length, False, False, ("execution.http_response",))
    except httpx.TimeoutException:
        return HttpObservation(ExecutionStatus.TIMEOUT, None, None, 0, False, False, ("execution.timeout",))
    except httpx.RequestError:
        return HttpObservation(ExecutionStatus.NETWORK_ERROR, None, None, 0, False, False, ("execution.network_error",))
