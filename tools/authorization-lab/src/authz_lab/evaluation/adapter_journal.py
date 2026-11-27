"""Durable, redacted execution reservation; existing execution is never replayed.

The operator owns the parent directory. A separate flock survives atomic rename
and prevents a second process from recovering an execution still being written.
This is a client checkpoint, never an independent HTTP delivery receipt.
"""
import fcntl
import json
import os
from pathlib import Path
import tempfile


class ExecutionJournal:
    def __init__(self, path, execution_id):
        self.path = Path(path)
        self.execution_id = execution_id
        self._lock_fd = None

    def __del__(self):
        self._release()

    def _acquire(self):
        if self._lock_fd is not None:
            return
        fd = os.open(str(self.path) + '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(fd)
            raise
        self._lock_fd = fd

    def _release(self):
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None

    def reserve(self):
        self._acquire()
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as stream:
                json.dump(dict(execution_id=self.execution_id, state='RESERVED', counts=[0, 0, 0]), stream)
                stream.flush()
                os.fsync(stream.fileno())
            self._sync_directory()
        except BaseException:
            self._release()
            raise

    def _sync_directory(self):
        fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def write(self, state, counts, digest=None):
        self._acquire()
        temp = None
        try:
            # Exclusive unique file: never follow a pre-existing .next symlink.
            fd, name = tempfile.mkstemp(prefix=self.path.name + '.', dir=self.path.parent)
            temp = Path(name)
            with os.fdopen(fd, 'w') as stream:
                json.dump(dict(schema_version=1, execution_id=self.execution_id, state=state,
                               counts=list(counts), content_digest=digest), stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
            self._sync_directory()
        except BaseException:
            self._release()
            raise
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        if state in ('COMPLETED', 'CANCELLED', 'FAILED', 'CRASH_RECOVERED'):
            self._release()

    def recover(self):
        self._acquire()
        try:
            # Torn reservation still forbids replay; never invent observed results.
            try:
                data = json.loads(self.path.read_text())
            except (ValueError, UnicodeError):
                data = {}
            if not isinstance(data, dict):
                raise ValueError('Invalid journal')
            if data.get('execution_id', self.execution_id) != self.execution_id:
                raise ValueError('Journal execution mismatch')
            counts = data.get('counts', [0, 0, 0])
            if (type(counts) is not list or len(counts) != 3
                    or any(type(v) is not int or v < 0 for v in counts)):
                raise ValueError('Invalid journal accounting')
            if data.get('state') not in ('COMPLETED', 'CANCELLED', 'FAILED', 'CRASH_RECOVERED'):
                self.write('CRASH_RECOVERED', counts)
            return json.loads(self.path.read_text())
        finally:
            self._release()
