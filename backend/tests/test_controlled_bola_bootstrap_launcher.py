"""Tests for the portable Controlled BOLA Lab Bash launcher."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = PROJECT_ROOT / "tools" / "run_controlled_bola_bootstrap.sh"


def _fake_python(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-python"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['CAPTURE_FILE']).write_text(json.dumps({'args': sys.argv[1:], 'target': os.environ['BOLA_TARGET_BASE_URL'], 'openapi': os.environ['BOLA_OPENAPI_PATH']}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def test_launcher_finds_project_root_and_forwards_options(tmp_path: Path) -> None:
    env_file = tmp_path / "launcher.env"
    env_file.write_text("AUTHZ_ADMIN_PASSWORD=from-env-file\n", encoding="utf-8")
    openapi = tmp_path / "reviewed.openapi.json"
    openapi.write_text("{}", encoding="utf-8")
    capture_file = tmp_path / "capture.json"

    environment = {
        **os.environ,
        "BOLA_ENV_FILE": str(env_file),
        "BOLA_PYTHON": str(_fake_python(tmp_path)),
        "BOLA_OPENAPI_PATH": str(openapi),
        "BOLA_USER_A_TOKEN": "token-a",
        "BOLA_USER_B_TOKEN": "token-b",
        "CAPTURE_FILE": str(capture_file),
    }
    result = subprocess.run(
        ["bash", str(LAUNCHER), "--health-smoke", "--verify-identities"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    captured = json.loads(capture_file.read_text(encoding="utf-8"))
    assert captured["args"] == [str(PROJECT_ROOT / "tools" / "bootstrap_controlled_bola_lab.py"), "--health-smoke", "--verify-identities"]
    assert captured["target"] == "http://100.106.64.21:5003"
    assert captured["openapi"] == str(openapi)
    assert "token-a" not in result.stdout + result.stderr
    assert "token-b" not in result.stdout + result.stderr


def test_launcher_rejects_invalid_env_without_evaluating_it(tmp_path: Path) -> None:
    env_file = tmp_path / "invalid.env"
    env_file.write_text("AUTHZ_ADMIN_PASSWORD=admin-secret\nthis is not valid shell input\n", encoding="utf-8")
    openapi = tmp_path / "reviewed.openapi.json"
    openapi.write_text("{}", encoding="utf-8")
    capture_file = tmp_path / "capture.json"

    result = subprocess.run(
        ["bash", str(LAUNCHER)],
        cwd=tmp_path,
        env={
            **os.environ,
            "BOLA_ENV_FILE": str(env_file),
            "BOLA_PYTHON": str(_fake_python(tmp_path)),
            "BOLA_OPENAPI_PATH": str(openapi),
            "BOLA_USER_A_TOKEN": "token-a",
            "BOLA_USER_B_TOKEN": "token-b",
            "CAPTURE_FILE": str(capture_file),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Invalid .env entry" in result.stderr
    assert "admin-secret" not in result.stderr
    assert not capture_file.exists()
