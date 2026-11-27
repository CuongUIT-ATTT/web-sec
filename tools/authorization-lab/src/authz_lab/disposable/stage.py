"""Fail-closed local lifecycle journal; interrupted claims require a fresh run.

No automatic recovery or retries. The local filesystem/operator is the trust boundary.
"""
from functools import wraps
import json
import os
from pathlib import Path

from .manifest import BflaManifestError, validate_run_id, validate_project_name


class StageConflict(BflaManifestError, FileExistsError):
    """Existing durable stage claim or receipt."""


def durable_json(path, value):
    """Publish a complete, fsynced record without replacing an existing artifact."""
    path = Path(path)
    temporary = path.with_name(path.name + '.pending')
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(value, handle, sort_keys=True, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.link(temporary, path)  # Atomic no-overwrite publication on the same filesystem.
    temporary.unlink()
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def check_stage(run_id, stage, results_root):
    directory = Path(results_root) / validate_run_id(run_id)
    names = ['.lifecycle-active', f'.{stage}-claimed', f'{stage}-stage.json']
    if stage == 'prepare':
        names += ['execution-receipt.json', 'extended-state-receipt.json']
    elif stage == 'execute':
        names += ['execution-receipt.json']
    elif stage == 'execute-extended':
        names += ['extended-state-receipt.json']
    elif stage == 'preflight':
        names += ['preflight-receipt.json']
    if any((directory / name).exists() or (directory / name).is_symlink() for name in names):
        raise StageConflict('Existing or interrupted lifecycle stage; use a fresh run.')
    return directory


def lifecycle(stage):
    def decorate(function):
        @wraps(function)
        def guarded(run_id, project, run_dir, results_root='results/bfla-disposable'):
            validate_project_name(project, validate_run_id(run_id))
            directory = check_stage(run_id, stage, results_root)
            active = directory / '.lifecycle-active'
            try:
                descriptor = os.open(active, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as error:
                raise BflaManifestError('Another lifecycle stage is active or interrupted.') from error
            os.close(descriptor)
            # Retain active lock on BaseException (including simulated abrupt exit).
            try:
                durable_json(directory / f'.{stage}-claimed', {'stage': stage, 'status': 'CLAIMED'})
                result = function(run_id, project, run_dir, results_root)
            except Exception:
                durable_json(directory / f'{stage}-stage.json', {
                    'stage': stage, 'status': 'FAILED', 'reason': 'STAGE_FAILED',
                    'credential_or_response_bodies_exported': False,
                })
                active.unlink()
                raise
            durable_json(directory / f'{stage}-stage.json', {
                'stage': stage, 'status': 'COMPLETE',
                'credential_or_response_bodies_exported': False,
            })
            active.unlink()
            return result
        return guarded
    return decorate
