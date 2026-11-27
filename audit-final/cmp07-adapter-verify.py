"""Run offline evaluation regression with network/process guards and hash checks."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
from unittest.mock import patch
import pytest

root = Path(__file__).resolve().parents[1]
paths = sorted((root / 'tools/authorization-lab/src/authz_lab/evaluation').glob('*.py')) + sorted((root / 'tools/authorization-lab/tests/evaluation').glob('*.py'))
def hashes():
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
def deny(*args, **kwargs):
    raise AssertionError('External I/O forbidden')
before = hashes()
with tempfile.TemporaryDirectory(prefix='cmp07-adapter-') as temp, \
     patch.multiple(socket, create_connection=deny, getaddrinfo=deny, gethostbyname=deny, gethostbyname_ex=deny), \
     patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
     patch.object(socket.socket, 'sendto', deny), patch.object(subprocess, 'Popen', deny), \
     patch.multiple(os, system=deny, fork=deny, posix_spawn=deny, posix_spawnp=deny):
    code = pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp', temp + '/pytest', str(root / 'tools/authorization-lab/tests/evaluation')])
after = hashes()
report = dict(exit_code=code, hashes_unchanged=before == after, before=before, after=after)
(root / 'audit-final/cmp07-adapter-verification.json').write_text(json.dumps(report, indent=2)+'\n')
raise SystemExit(code if before == after else 99)
