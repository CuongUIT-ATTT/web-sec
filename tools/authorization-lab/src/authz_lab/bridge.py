"""Operator-side Unix-socket bridge for one fixed VAmPI read-only workflow.

This module intentionally has no BFLA, ZAP, Docker, generic command, or arbitrary
network-target support. FastAPI talks to this service over an operator-owned Unix
socket; the service alone may launch the fixed read-only CLI command.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .common import TOKEN_PATTERN
from .read_only.request_runner import ALLOWED_BASE_URL, validate_base_url

JOB_KIND = "READ_ONLY_VAMPI_VERIFICATION_V1"
PROTOCOL_VERSION = 1
WEB_AUDIENCE = "web-to-bridge"
CALLBACK_AUDIENCE = "bridge-to-web"
MAX_REQUEST_BYTES = 4096
MAX_ARTIFACT_BYTES = 262_144
ALLOWED_ARTIFACTS = frozenset({
    "endpoint_inventory.json", "ownership_map.json", "test_matrix.json", "preflight.json",
    "raw_results.json", "final_report.json", "read_only_verification_timing.json",
    "manual_verification.json", "independent_verification_findings.json",
    "read_only_verification_comparison.json",
})
PUBLIC_ID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27}$")
TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"})
ACTIVE_STATUSES = frozenset({"SUBMITTED", "RUNNING", "CANCEL_REQUESTED"})


class BridgeError(RuntimeError):
    """A safe, non-sensitive bridge failure."""


@dataclass(frozen=True)
class BridgeConfig:
    socket_path: Path
    shared_secret: str
    callback_url: str
    executable: Path
    spec_path: Path
    roles_path: Path
    ownership_path: Path
    artifact_root: Path
    journal_path: Path

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> "BridgeConfig":
        values = os.environ if environ is None else environ
        required = {
            "AUTHZ_LAB_BRIDGE_SOCKET_PATH": "socket path",
            "AUTHZ_LAB_BRIDGE_SHARED_SECRET": "shared secret",
            "AUTHZ_LAB_BRIDGE_CALLBACK_URL": "callback URL",
            "AUTHZ_LAB_BRIDGE_EXECUTABLE": "CLI executable",
            "AUTHZ_LAB_BRIDGE_SPEC": "reviewed OpenAPI JSON",
            "AUTHZ_LAB_BRIDGE_ROLES_CONFIG": "roles config",
            "AUTHZ_LAB_BRIDGE_OWNERSHIP": "ownership CSV",
            "AUTHZ_LAB_BRIDGE_ARTIFACT_ROOT": "artifact root",
            "AUTHZ_LAB_BRIDGE_JOURNAL": "bridge journal",
        }
        missing = [label for name, label in required.items() if not values.get(name, "").strip()]
        if missing:
            raise BridgeError("Missing bridge configuration: " + ", ".join(missing))
        secret = values["AUTHZ_LAB_BRIDGE_SHARED_SECRET"]
        if len(secret) < 32:
            raise BridgeError("Bridge shared secret must be at least 32 characters.")
        callback_url = values["AUTHZ_LAB_BRIDGE_CALLBACK_URL"].rstrip("/")
        if not callback_url.startswith("http://127.0.0.1:"):
            raise BridgeError("Bridge callback URL must use loopback 127.0.0.1 HTTP.")
        executable = Path(values["AUTHZ_LAB_BRIDGE_EXECUTABLE"])
        if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
            raise BridgeError("Bridge executable must be an absolute executable file.")
        inputs = [Path(values[name]) for name in ("AUTHZ_LAB_BRIDGE_SPEC", "AUTHZ_LAB_BRIDGE_ROLES_CONFIG", "AUTHZ_LAB_BRIDGE_OWNERSHIP")]
        if any(not path.is_absolute() or not path.is_file() for path in inputs):
            raise BridgeError("Bridge inputs must be existing absolute operator-owned files.")
        artifact_root = Path(values["AUTHZ_LAB_BRIDGE_ARTIFACT_ROOT"])
        journal_path = Path(values["AUTHZ_LAB_BRIDGE_JOURNAL"])
        socket_path = Path(values["AUTHZ_LAB_BRIDGE_SOCKET_PATH"])
        if not socket_path.is_absolute() or not artifact_root.is_absolute() or not journal_path.is_absolute():
            raise BridgeError("Bridge socket, artifact, and journal paths must be absolute.")
        artifact_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        journal_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        return cls(
            socket_path=socket_path,
            shared_secret=secret,
            callback_url=callback_url,
            executable=executable,
            spec_path=inputs[0],
            roles_path=inputs[1],
            ownership_path=inputs[2],
            artifact_root=artifact_root.resolve(),
            journal_path=journal_path.resolve(),
        )


def _signature(secret: str, method: str, path: str, body: bytes, timestamp: str, nonce: str, audience: str) -> str:
    digest = hashlib.sha256(body).hexdigest()
    message = "\n".join((method.upper(), path, digest, timestamp, nonce, audience)).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _validate_signed_headers(headers: dict[str, str], body: bytes, secret: str, *, method: str, path: str, audience: str) -> None:
    timestamp = headers.get("x-bridge-timestamp", "")
    nonce = headers.get("x-bridge-nonce", "")
    signature = headers.get("x-bridge-signature", "")
    if headers.get("x-bridge-audience") != audience or not nonce or len(nonce) > 128:
        raise BridgeError("Bridge authentication failed.")
    try:
        if abs(int(time.time()) - int(timestamp)) > 60:
            raise BridgeError("Bridge authentication failed.")
    except ValueError as error:
        raise BridgeError("Bridge authentication failed.") from error
    expected = _signature(secret, method, path, body, timestamp, nonce, audience)
    if not hmac.compare_digest(expected, signature):
        raise BridgeError("Bridge authentication failed.")


def _read_journal(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BridgeError("Bridge journal is unreadable.") from error
    if not isinstance(value, dict):
        raise BridgeError("Bridge journal is invalid.")
    return {str(key): item for key, item in value.items() if isinstance(item, dict)}


def _write_journal(path: Path, journal: dict[str, dict[str, Any]]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(journal, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _artifact_summary(directory: Path) -> tuple[dict[str, Any], str]:
    manifest: dict[str, str] = {}
    outcome_counts: dict[str, int] = {}
    case_count = 0
    for artifact in directory.iterdir():
        if artifact.name not in ALLOWED_ARTIFACTS or not artifact.is_file() or artifact.stat().st_size > MAX_ARTIFACT_BYTES:
            raise BridgeError("Bridge artifact validation failed.")
        raw = artifact.read_bytes()
        if TOKEN_PATTERN.search(raw.decode("utf-8", errors="ignore")):
            raise BridgeError("Bridge artifact validation failed.")
        manifest[artifact.name] = hashlib.sha256(raw).hexdigest()
        if artifact.name == "final_report.json":
            report = json.loads(raw.decode("utf-8"))
            if not isinstance(report, list):
                raise BridgeError("Bridge artifact validation failed.")
            case_count = len(report)
            for item in report:
                if isinstance(item, dict) and isinstance(item.get("verdict"), str):
                    verdict = item["verdict"]
                    outcome_counts[verdict] = outcome_counts.get(verdict, 0) + 1
    required = {"preflight.json", "final_report.json", "read_only_verification_timing.json"}
    if not required.issubset(manifest):
        raise BridgeError("Bridge artifact validation failed.")
    encoded_manifest = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "case_count": case_count,
        "outcome_counts": outcome_counts,
        "preflight_passed": True,
        "redaction_verified": True,
        "target_label": "LOCAL_VAMPI_READ_ONLY",
    }, hashlib.sha256(encoded_manifest).hexdigest()


class ReadOnlyLabBridge:
    """Single-worker bridge with an idempotent public-ID journal and callback outbox."""

    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.journal = _read_journal(config.journal_path)
        self.active_process: asyncio.subprocess.Process | None = None
        self.active_public_id: str | None = None
        self.cancel_requested: set[str] = set()
        self.seen_nonces: dict[str, int] = {}
        self.lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()

    def _save(self) -> None:
        _write_journal(self.config.journal_path, self.journal)

    def _task(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def recover(self) -> None:
        """Never replay unknown children; emit terminal interruption through the outbox."""
        async with self.lock:
            for public_id, record in self.journal.items():
                if record.get("status") in ACTIVE_STATUSES:
                    sequence = int(record.get("sequence", 0)) + 1
                    record["status"] = "INTERRUPTED"
                    record["sequence"] = sequence
                    record["pending_event"] = {
                        "sequence": sequence,
                        "status": "INTERRUPTED",
                        "finished_at": int(time.time()),
                        "failure_code": "INTERRUPTED",
                        "summary": {"target_label": "LOCAL_VAMPI_READ_ONLY"},
                    }
            self._save()
        await self.retry_pending_callbacks()

    async def retry_pending_callbacks(self) -> None:
        async with self.lock:
            pending = [(public_id, record["pending_event"]) for public_id, record in self.journal.items() if isinstance(record.get("pending_event"), dict)]
        for public_id, event in pending:
            if await self._callback(public_id, event):
                async with self.lock:
                    record = self.journal.get(public_id)
                    if record is not None and record.get("pending_event") == event:
                        record.pop("pending_event", None)
                        self._save()

    async def claim_nonce(self, nonce: str) -> None:
        """Reject a repeated web-to-bridge request within its HMAC validity window."""
        now = int(time.time())
        async with self.lock:
            self.seen_nonces = {
                candidate: expires_at
                for candidate, expires_at in self.seen_nonces.items()
                if expires_at >= now
            }
            if nonce in self.seen_nonces:
                raise BridgeError("Bridge request replay rejected.")
            self.seen_nonces[nonce] = now + 60

    async def submit(self, payload: dict[str, Any]) -> None:
        if set(payload) != {"public_id", "job_kind", "protocol_version"}:
            raise BridgeError("Unsupported bridge job request.")
        public_id = payload.get("public_id")
        if not isinstance(public_id, str) or not PUBLIC_ID_PATTERN.fullmatch(public_id):
            raise BridgeError("Unsupported bridge job request.")
        if payload.get("job_kind") != JOB_KIND or payload.get("protocol_version") != PROTOCOL_VERSION:
            raise BridgeError("Unsupported bridge job request.")
        async with self.lock:
            if public_id in self.journal:
                return
            if self.active_public_id is not None:
                raise BridgeError("A read-only bridge job is already active.")
            self.journal[public_id] = {"status": "SUBMITTED", "sequence": 0}
            self._save()
            self.active_public_id = public_id
            self._task(self._run(public_id))

    async def cancel(self, public_id: str) -> None:
        async with self.lock:
            if public_id != self.active_public_id:
                return
            self.cancel_requested.add(public_id)
            record = self.journal.get(public_id)
            if record is not None and record.get("status") not in TERMINAL_STATUSES:
                record["status"] = "CANCEL_REQUESTED"
                self._save()
            if self.active_process is not None and self.active_process.returncode is None:
                self.active_process.send_signal(signal.SIGTERM)

    async def _callback(self, public_id: str, event: dict[str, Any]) -> bool:
        path = f"/api/internal/bridge/jobs/{public_id}/events"
        body = json.dumps(event, separators=(",", ":"), sort_keys=True).encode("utf-8")
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(24)
        signature = _signature(self.config.shared_secret, "POST", path, body, timestamp, nonce, CALLBACK_AUDIENCE)

        def post() -> None:
            request = Request(
                self.config.callback_url + path,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-Bridge-Timestamp": timestamp,
                    "X-Bridge-Nonce": nonce,
                    "X-Bridge-Audience": CALLBACK_AUDIENCE,
                    "X-Bridge-Signature": signature,
                },
            )
            with urlopen(request, timeout=5) as response:
                response.read(0)

        try:
            await asyncio.to_thread(post)
        except (HTTPError, URLError, OSError):
            return False
        return True

    async def _record_event(self, public_id: str, event: dict[str, Any]) -> None:
        async with self.lock:
            record = self.journal[public_id]
            record["status"] = event["status"]
            record["sequence"] = event["sequence"]
            record["pending_event"] = event
            self._save()
        await self.retry_pending_callbacks()

    async def _run(self, public_id: str) -> None:
        started = int(time.time())
        sequence = 1
        terminal: dict[str, Any]
        try:
            directory = (self.config.artifact_root / public_id).resolve()
            if directory.parent != self.config.artifact_root or directory.exists():
                raise BridgeError("Bridge artifact directory rejected.")
            directory.mkdir(mode=0o700)
            await self._record_event(public_id, {
                "sequence": sequence,
                "status": "RUNNING",
                "started_at": started,
                "summary": {"target_label": "LOCAL_VAMPI_READ_ONLY"},
            })
            if public_id in self.cancel_requested:
                terminal = {
                    "sequence": sequence + 1,
                    "status": "CANCELLED",
                    "started_at": started,
                    "finished_at": int(time.time()),
                    "failure_code": "CANCELLED",
                    "summary": {"target_label": "LOCAL_VAMPI_READ_ONLY"},
                }
            else:
                validate_base_url(ALLOWED_BASE_URL)
                argv = [
                    str(self.config.executable), "verify-workflow", "--spec", str(self.config.spec_path),
                    "--roles-config", str(self.config.roles_path), "--ownership", str(self.config.ownership_path),
                    "--output-dir", str(directory), "--base-url", ALLOWED_BASE_URL,
                ]
                self.active_process = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    env={"PATH": str(self.config.executable.parent), "PYTHONUNBUFFERED": "1"},
                    start_new_session=True,
                )
                return_code = await self.active_process.wait()
                finished = int(time.time())
                if return_code == 0:
                    summary, manifest_hash = _artifact_summary(directory)
                    summary["elapsed_ms"] = (finished - started) * 1000
                    terminal = {
                        "sequence": sequence + 1,
                        "status": "SUCCEEDED",
                        "started_at": started,
                        "finished_at": finished,
                        "summary": summary,
                        "artifact_manifest_sha256": manifest_hash,
                    }
                else:
                    terminal = {
                        "sequence": sequence + 1,
                        "status": "CANCELLED" if public_id in self.cancel_requested else "FAILED",
                        "started_at": started,
                        "finished_at": finished,
                        "failure_code": "CANCELLED" if public_id in self.cancel_requested else "CLI_FAILED",
                        "summary": {"target_label": "LOCAL_VAMPI_READ_ONLY"},
                    }
        except BridgeError:
            terminal = {
                "sequence": sequence + 1,
                "status": "FAILED",
                "started_at": started,
                "finished_at": int(time.time()),
                "failure_code": "ARTIFACT_VALIDATION_FAILED",
                "summary": {"target_label": "LOCAL_VAMPI_READ_ONLY"},
            }
        except (OSError, ValueError):
            terminal = {
                "sequence": sequence + 1,
                "status": "FAILED",
                "started_at": started,
                "finished_at": int(time.time()),
                "failure_code": "CLI_FAILED",
                "summary": {"target_label": "LOCAL_VAMPI_READ_ONLY"},
            }
        finally:
            self.active_process = None
            self.active_public_id = None
            self.cancel_requested.discard(public_id)
        await self._record_event(public_id, terminal)


async def _read_request(reader: asyncio.StreamReader) -> tuple[str, str, dict[str, str], bytes]:
    request_line = (await reader.readline()).decode("ascii", errors="replace").strip().split()
    if len(request_line) != 3 or request_line[2] != "HTTP/1.1":
        raise BridgeError("Malformed bridge request.")
    headers: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if line == b"\r\n":
            break
        name, separator, value = line.decode("ascii", errors="replace").partition(":")
        if not separator or not name:
            raise BridgeError("Malformed bridge request.")
        headers[name.lower()] = value.strip()
    try:
        length = int(headers.get("content-length", "0"))
    except ValueError as error:
        raise BridgeError("Malformed bridge request.") from error
    if length < 0 or length > MAX_REQUEST_BYTES:
        raise BridgeError("Bridge request too large.")
    return request_line[0], request_line[1], headers, await reader.readexactly(length)


async def serve(config: BridgeConfig) -> None:
    if config.socket_path.exists():
        raise BridgeError("Bridge socket path already exists.")
    config.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    bridge = ReadOnlyLabBridge(config)
    await bridge.recover()

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            method, path, headers, body = await _read_request(reader)
            _validate_signed_headers(headers, body, config.shared_secret, method=method, path=path, audience=WEB_AUDIENCE)
            await bridge.claim_nonce(headers["x-bridge-nonce"])
            if method == "POST" and path == "/v1/jobs":
                payload = json.loads(body)
                if not isinstance(payload, dict):
                    raise BridgeError("Unsupported bridge job request.")
                await bridge.submit(payload)
            elif method == "POST" and path.startswith("/v1/jobs/") and path.endswith("/cancel"):
                public_id = path.removeprefix("/v1/jobs/").removesuffix("/cancel")
                if not PUBLIC_ID_PATTERN.fullmatch(public_id) or body != b"{}":
                    raise BridgeError("Unsupported bridge request.")
                await bridge.cancel(public_id)
            else:
                raise BridgeError("Unsupported bridge request.")
            writer.write(b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        except (BridgeError, ValueError, asyncio.IncompleteReadError):
            writer.write(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        finally:
            await writer.drain()
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_unix_server(handler, path=str(config.socket_path))
    os.chmod(config.socket_path, 0o660)
    try:
        async with server:
            await server.serve_forever()
    finally:
        if config.socket_path.exists():
            config.socket_path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Operator-side fixed VAmPI read-only Unix-socket bridge.")
    parser.parse_args(argv)
    try:
        asyncio.run(serve(BridgeConfig.from_environment()))
    except KeyboardInterrupt:
        return 0
    except BridgeError as error:
        print(f"Bridge stopped safely: {error}", file=sys.stderr)
        return 2
    return 0
