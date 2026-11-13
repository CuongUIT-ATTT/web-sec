"""Dispatch fixed read-only lab jobs to the operator-owned Unix-socket bridge."""

from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy.orm import sessionmaker

from backend.app.core.settings import Settings
from backend.app.external_lab.contracts import WEB_REQUEST_AUDIENCE, signed_headers
from backend.app.external_lab.service import cancellation_requests, claim_next_job, mark_orphaned_jobs, mark_submission_failed, mark_submitted

LOGGER = logging.getLogger(__name__)


async def _bridge_request(settings: Settings, *, path: str, payload: dict[str, object]) -> None:
    """Send one allowlisted bridge request over the configured Unix socket."""
    if settings.external_lab_bridge_socket_path is None:
        raise RuntimeError("Bridge socket path is missing.")
    body, signature = signed_headers(
        settings.external_lab_bridge_shared_secret,
        method="POST",
        path=path,
        payload=payload,
        audience=WEB_REQUEST_AUDIENCE,
    )
    reader, writer = await asyncio.wait_for(
        asyncio.open_unix_connection(str(settings.external_lab_bridge_socket_path)), timeout=3
    )
    try:
        request = (
            f"POST {path} HTTP/1.1\r\n"
            "Host: local-bridge\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"X-Bridge-Timestamp: {signature.timestamp}\r\n"
            f"X-Bridge-Nonce: {signature.nonce}\r\n"
            f"X-Bridge-Audience: {signature.audience}\r\n"
            f"X-Bridge-Signature: {signature.signature}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii") + body
        writer.write(request)
        await writer.drain()
        status_line = await asyncio.wait_for(reader.readline(), timeout=5)
        if not status_line.startswith(b"HTTP/1.1 20"):
            raise RuntimeError("Bridge rejected fixed read-only job request.")
    finally:
        writer.close()
        await writer.wait_closed()


async def _submit_job(settings: Settings, *, public_id: str, job_kind: str, protocol_version: int) -> None:
    """Send the only supported fixed-workflow bridge submission."""
    await _bridge_request(
        settings,
        path="/v1/jobs",
        payload={"public_id": public_id, "job_kind": job_kind, "protocol_version": protocol_version},
    )


async def _cancel_job(settings: Settings, public_id: str) -> None:
    await _bridge_request(settings, path=f"/v1/jobs/{public_id}/cancel", payload={})


async def external_lab_dispatcher_loop(session_factory: sessionmaker, settings: Settings, stop_event: asyncio.Event) -> None:
    """Claim once, dispatch once, and never replay uncertain operator-side execution."""
    with session_factory.begin() as session:
        mark_orphaned_jobs(session)
    while not stop_event.is_set():
        with session_factory.begin() as session:
            cancellations = [job.public_id for job in cancellation_requests(session)]
            job = claim_next_job(session)
            job_data = None if job is None else (job.public_id, job.job_kind, job.protocol_version)
        for public_id in cancellations:
            try:
                await _cancel_job(settings, public_id)
            except Exception:
                LOGGER.warning("External read-only lab bridge cancellation failed: job=%s", public_id)
        if job_data is None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.25)
            except TimeoutError:
                continue
            continue
        public_id, job_kind, protocol_version = job_data
        try:
            await _submit_job(settings, public_id=public_id, job_kind=job_kind, protocol_version=protocol_version)
            with session_factory.begin() as session:
                mark_submitted(session, public_id)
        except Exception:
            LOGGER.warning("External read-only lab bridge submission failed: job=%s", public_id)
            with session_factory.begin() as session:
                mark_submission_failed(session, public_id, "BRIDGE_UNAVAILABLE")
