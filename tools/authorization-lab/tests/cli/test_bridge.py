import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from authz_lab import bridge


def config(tmp_path: Path) -> bridge.BridgeConfig:
    executable = tmp_path / "vampi-authz-lab"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o700)
    spec = tmp_path / "spec.json"
    roles = tmp_path / "roles.json"
    ownership = tmp_path / "ownership.csv"
    for path in (spec, roles, ownership):
        path.write_text("{}", encoding="utf-8")
    return bridge.BridgeConfig(
        socket_path=tmp_path / "bridge.sock",
        shared_secret="s" * 32,
        callback_url="http://127.0.0.1:8000",
        executable=executable,
        spec_path=spec,
        roles_path=roles,
        ownership_path=ownership,
        artifact_root=tmp_path / "artifacts",
        journal_path=tmp_path / "journal.json",
    )


def payload(public_id: str = "12345678-1234-1234-1234-123456789abc") -> dict[str, object]:
    return {
        "public_id": public_id,
        "job_kind": bridge.JOB_KIND,
        "protocol_version": bridge.PROTOCOL_VERSION,
    }


def test_nonce_claim_rejects_replay(tmp_path: Path) -> None:
    instance = bridge.ReadOnlyLabBridge(config(tmp_path))

    async def exercise() -> None:
        await instance.claim_nonce("request-nonce")
        with pytest.raises(bridge.BridgeError):
            await instance.claim_nonce("request-nonce")

    asyncio.run(exercise())


def test_submit_rejects_any_generic_execution_fields(tmp_path: Path) -> None:
    instance = bridge.ReadOnlyLabBridge(config(tmp_path))

    async def exercise() -> None:
        with pytest.raises(bridge.BridgeError):
            await instance.submit({**payload(), "argv": ["sh"]})

    asyncio.run(exercise())


def test_run_uses_exact_fixed_argv_and_never_shell(tmp_path: Path) -> None:
    configuration = config(tmp_path)
    configuration.artifact_root.mkdir()
    instance = bridge.ReadOnlyLabBridge(configuration)
    public_id = payload()["public_id"]
    instance.journal[str(public_id)] = {"status": "SUBMITTED", "sequence": 0}
    captured: dict[str, object] = {}

    class Process:
        returncode = 1

        async def wait(self) -> int:
            return 1

    async def create_process(*argv: str, **kwargs: object) -> Process:
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return Process()

    async def callback(_public_id: str, _event: dict[str, object]) -> bool:
        return True

    async def exercise() -> None:
        with patch("authz_lab.bridge.asyncio.create_subprocess_exec", new=create_process), patch.object(instance, "_callback", new=callback):
            await instance._run(str(public_id))

    asyncio.run(exercise())

    argv = captured["argv"]
    assert argv == (
        str(configuration.executable), "verify-workflow", "--spec", str(configuration.spec_path),
        "--roles-config", str(configuration.roles_path), "--ownership", str(configuration.ownership_path),
        "--output-dir", str(configuration.artifact_root / public_id), "--base-url", bridge.ALLOWED_BASE_URL,
    )
    kwargs = captured["kwargs"]
    assert "shell" not in kwargs
    assert kwargs["start_new_session"] is True
    assert kwargs["env"] == {"PATH": str(configuration.executable.parent), "PYTHONUNBUFFERED": "1"}
    assert instance.journal[str(public_id)]["status"] == "FAILED"


def test_recover_marks_unknown_active_work_interrupted_without_launching(tmp_path: Path) -> None:
    configuration = config(tmp_path)
    configuration.journal_path.write_text(
        json.dumps({payload()["public_id"]: {"status": "RUNNING", "sequence": 4}}),
        encoding="utf-8",
    )
    instance = bridge.ReadOnlyLabBridge(configuration)

    async def callback(_public_id: str, _event: dict[str, object]) -> bool:
        return True

    async def exercise() -> None:
        with patch.object(instance, "_callback", new=callback):
            await instance.recover()

    asyncio.run(exercise())
    record = instance.journal[str(payload()["public_id"])]
    assert record["status"] == "INTERRUPTED"
    assert record["sequence"] == 5
    assert "pending_event" not in record
