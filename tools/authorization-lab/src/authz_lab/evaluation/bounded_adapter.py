"""Offline-plannable CMP07 adapter. No default transport, login or discovery.

A transport must dispatch exactly one GET without redirects/retries and expose
async read(n)/close(). Cancellation must abort its underlying I/O. This module
never authorizes a target: operator approval and principal attestation are inputs.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import math
import re
import time
from urllib.parse import urlsplit

from .case_manifest import CaseManifest, _digest
from .importer import import_bundle, _pairs
from .observations import Observation, Provenance, _opaque


@dataclass(frozen=True)
class Principal:
    alias: str
    role: str
    username: str
    verified: bool


@dataclass(frozen=True)
class Mapping:
    case_id: str
    path: str
    principal: str
    owner_principal: str | None = None
    object_path: tuple[str, ...] = ()
    object_value: str | None = None
    owner_path: tuple[str, ...] = ()
    sensitive_paths: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Approval:
    origin: str
    paths: tuple[str, ...]
    manifest_digest: str
    mapping_digest: str
    principal_digest: str
    execution_id: str
    source_hash: str
    total_cap: int
    phase_caps: tuple[int, int, int]  # identity, baseline, case
    expires_at: float
    timeout: float = 2.0
    body_limit: int = 65536


def principal_digest(principals):
    from dataclasses import asdict
    return _digest([asdict(p) for p in sorted(principals, key=lambda p: p.alias)])


def mapping_digest(mappings):
    from dataclasses import asdict
    return _digest([asdict(m) for m in sorted(mappings, key=lambda m: m.case_id)])


def _get(body, path):
    for key in path:
        if type(body) is not dict or key not in body:
            return None
        body = body[key]
    return body


def _present(value):
    return type(value) in (str, int, bool) and value != ''


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('Non-finite JSON number')
    return value


def _shape(body):
    counts = dict(object=0, array=0, string=0, number=0, boolean=0, null=0)
    def visit(value):
        kind = {dict: 'object', list: 'array', str: 'string', int: 'number',
                float: 'number', bool: 'boolean', type(None): 'null'}[type(value)]
        counts[kind] += 1
        for child in value.values() if type(value) is dict else value if type(value) is list else ():
            visit(child)
    visit(body)
    return counts


class BoundedAdapter:
    """Single-use, sequential executor; count failures before dispatch, retry zero.

    Frozen mappings include explicit owner principals and exact fixture object
    identity. No inference by role, URL template or historical execution occurs.
    """
    def __init__(self, manifest, mappings, principals, approval, *, clock=time.time):
        if (type(manifest) is not CaseManifest or type(approval) is not Approval
                or any(type(m) is not Mapping for m in mappings)
                or any(type(p) is not Principal for p in principals)):
            raise ValueError('Frozen contracts required')
        self.manifest, self.approval, self.clock = manifest, approval, clock
        self.mappings, self.principals = tuple(mappings), tuple(principals)
        self.used = False
        self.counts = [0, 0, 0]
        self._validate()

    def _validate(self):
        a = self.approval
        origin = urlsplit(a.origin)
        if (origin.scheme not in ('http', 'https') or not origin.hostname
                or origin.username or origin.password or origin.path or origin.query
                or origin.fragment or a.origin != f'{origin.scheme}://{origin.netloc}'):
            raise ValueError('Invalid exact origin')
        try:
            local = origin.hostname == 'localhost' or ipaddress.ip_address(origin.hostname).is_loopback
        except ValueError:
            local = False
        if not local:
            raise ValueError('Loopback lab origin required')
        _opaque(a.execution_id, 'execution')
        if not re.fullmatch('[0-9a-f]{64}', a.source_hash):
            raise ValueError('Invalid source hash')
        if (a.manifest_digest != self.manifest.content_digest
                or a.mapping_digest != mapping_digest(self.mappings)
                or a.principal_digest != principal_digest(self.principals)):
            raise ValueError('Frozen digest mismatch')
        if (type(a.total_cap) is not int or a.total_cap < 1
                or type(a.phase_caps) is not tuple or len(a.phase_caps) != 3
                or any(type(v) is not int or v < 0 for v in a.phase_caps)
                or type(a.timeout) not in (int, float) or not 0 < a.timeout <= 30
                or type(a.expires_at) not in (int, float) or not math.isfinite(a.expires_at)
                or type(a.body_limit) is not int
                or not 1 <= a.body_limit <= 1048576 or not a.expires_at > self.clock()):
            raise ValueError('Invalid limits or expired approval')
        paths = a.paths
        if (type(paths) is not tuple or len(paths) != len(set(paths)) or '/me' not in paths
                or any(not re.fullmatch(r'/(?:me|books/v1/[A-Za-z0-9_-]+|users/v1/[A-Za-z0-9_-]+)', p) for p in paths)):
            raise ValueError('Exact path allowlist required')
        if (len({p.alias for p in self.principals}) != len(self.principals)
                or len({p.username for p in self.principals}) != len(self.principals)):
            raise ValueError('Duplicate principal')
        self.ps = {p.alias: p for p in self.principals}
        if any(type(p) is not Principal or p.verified is not True or not p.username for p in self.principals):
            raise ValueError('Verified principal required')
        if len({m.case_id for m in self.mappings}) != len(self.mappings) or {m.case_id for m in self.mappings} != {c.case_id for c in self.manifest.cases}:
            raise ValueError('Exact case mapping required')
        aliases = {}
        owners = {}
        for m in self.mappings:
            c = self.manifest.require_case(m.case_id)
            if (type(m.sensitive_paths) is not tuple
                    or any(type(path) is not tuple or any(type(k) is not str or not k for k in path)
                           for path in (m.object_path, m.owner_path, *m.sensitive_paths))):
                raise ValueError('Immutable field paths required')
            if c.method != 'GET' or m.path not in paths or m.principal not in self.ps:
                raise ValueError('Out of scope mapping')
            p = self.ps[m.principal]
            if p.role != c.actor_role or aliases.setdefault(c.actor_alias, p.alias) != p.alias:
                raise ValueError('Actor mismatch')
            if c.operation_template == '/me':
                valid = m.path == '/me' and c.owner_category == 'NONE'
            elif c.operation_template == '/users/v1/{username}':
                valid = m.path.startswith('/users/v1/') and c.owner_category == 'PUBLIC'
            elif c.operation_template == '/books/v1/{book_title}':
                valid = m.path.startswith('/books/v1/') and c.owner_category in ('SELF', 'OTHER') and c.actor_role != 'admin'
            else:
                valid = False
            if not valid:
                raise ValueError('Unreviewed policy or template')
            if c.owner_category in ('SELF', 'OTHER'):
                if (m.owner_principal not in self.ps or not m.object_path or not m.object_value
                        or not m.owner_path or not m.sensitive_paths
                        or any(not path for path in m.sensitive_paths)
                        or (c.owner_category == 'SELF') != (m.principal == m.owner_principal)):
                    raise ValueError('Owner baseline mapping required')
                key = (m.owner_principal, m.path, c.fixture_hash, m.object_path,
                       m.object_value, m.owner_path, m.sensitive_paths)
                if owners.setdefault(c.owner_alias, key) != key:
                    raise ValueError('Owner fixture mismatch')
        # Multiple profile aliases per role must resolve to the same principal.
        for role in {c.actor_role for c in self.manifest.cases}:
            if len({m.principal for m in self.mappings if self.manifest.require_case(m.case_id).actor_role == role}) != 1:
                raise ValueError('Role principal mismatch')

    def _sequence(self):
        steps = [(0, None, '/me', p) for p in sorted({m.principal for m in self.mappings} | {m.owner_principal for m in self.mappings if m.owner_principal})]
        # Baselines intentionally not reused: every case has explicit fixture linkage.
        steps += [(1, m.case_id, m.path, m.owner_principal) for m in self.mappings if m.owner_principal]
        steps += [(2, m.case_id, m.path, m.principal) for m in self.mappings]
        return steps

    def dry_plan(self):
        self._validate()
        steps = self._sequence()
        counts = [sum(s[0] == i for s in steps) for i in range(3)]
        return dict(method='GET', sequence=tuple(steps), total=len(steps), phases=counts,
                    total_cap=self.approval.total_cap, phase_caps=self.approval.phase_caps,
                    fits=len(steps) <= self.approval.total_cap and all(n <= cap for n, cap in zip(counts, self.approval.phase_caps)),
                    concurrency=1, retries=0, baseline_reuse=False)

    async def run(self, transport, *, cancelled=lambda: False, journal=None):
        """Cancellation propagates; terminal_receipt and optional journal retain audit.

        A durable journal is required at an operational boundary needing crash
        accounting. Existing reservations reject before any transport dispatch.
        """
        if self.used:
            raise ValueError('Single use execution')
        if journal is not None:
            if journal.execution_id != self.approval.execution_id:
                raise ValueError('Journal execution mismatch')
            journal.reserve()
        self._journal = journal
        self.terminal_receipt = None
        try:
            result = await self._run(transport, cancelled=cancelled)
        except BaseException as exc:
            state = 'CANCELLED' if isinstance(exc, asyncio.CancelledError) else 'FAILED'
            self.terminal_receipt = dict(execution_id=self.approval.execution_id,
                                         state=state, counts=tuple(self.counts))
            if journal is not None:
                journal.write(state, self.counts)
            raise
        state = 'CANCELLED' if result['stop'] == 'CANCELLED_OR_EXPIRED' else 'COMPLETED'
        self.terminal_receipt = dict(execution_id=self.approval.execution_id,
                                     state=state, counts=tuple(self.counts),
                                     content_digest=result['content_digest'])
        if journal is not None:
            journal.write(state, self.counts, result['content_digest'])
        return result

    async def _run(self, transport, *, cancelled=lambda: False):
        if self.used:
            raise ValueError('Single use execution')
        self._validate()
        self.used = True
        a = self.approval
        identities, baselines, results = {}, {}, {}
        body_observations = {}
        stop = None

        async def request(path, principal, observation, phase):
            nonlocal stop
            response = None
            try:
                response = await transport.get(a.origin + path, principal=principal,
                                               follow_redirects=False, retries=0)
                observation['http_status'] = response.status
                if response.status != 200 and not (phase == 2 and response.status == 403):
                    observation['failure'] = 'HTTP_STATUS'
                    raise ValueError('Invalid response')
                data = bytearray()
                while True:
                    chunk = await response.read(min(4096, a.body_limit + 1 - len(data)))
                    if type(chunk) is not bytes:
                        raise ValueError('Invalid body')
                    data.extend(chunk)
                    observation['bytes_observed'] = len(data)
                    if cancelled():
                        stop = 'CANCELLED_OR_EXPIRED'
                        observation['failure'] = 'CANCELLED'
                        raise ValueError('Cancellation')
                    if len(data) > a.body_limit:
                        observation['failure'] = 'BODY_LIMIT'
                        raise ValueError('Body limit')
                    if not chunk:
                        break
                observation['complete'] = True
                if response.content_type.split(';')[0].strip().lower() != 'application/json':
                    observation['failure'] = 'NON_JSON'
                    raise ValueError('Invalid content type')
                body = json.loads(data.decode('utf-8'), object_pairs_hook=_pairs, parse_float=_finite_float,
                                  parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON')))
                observation['json_valid'] = True
                observation['shape_counts'] = _shape(body)
                if type(body) is not dict or any(k in body for k in ('error', 'errors', 'message')):
                    raise ValueError('Invalid object')
                return body
            finally:
                if response is not None:
                    await response.close()
                    if cancelled():
                        stop = 'CANCELLED_OR_EXPIRED'

        for phase, case_id, path, principal in self._sequence():
            if cancelled() or self.clock() >= a.expires_at:
                stop = 'CANCELLED_OR_EXPIRED'
            if sum(self.counts) >= a.total_cap or self.counts[phase] >= a.phase_caps[phase]:
                stop = stop or 'CAP_EXHAUSTED'
            if stop:
                break
            self.counts[phase] += 1
            if self._journal is not None:
                self._journal.write('ATTEMPTING', self.counts)
            observation = dict(http_status=None, bytes_observed=0, complete=False, json_valid=False,
                               failure=None, normalization='json-typed-v1-no-fields-ignored',
                               wholebody_equal=None, confidence='INSUFFICIENT')
            if phase == 2:
                body_observations[case_id] = observation
            try:
                body = await asyncio.wait_for(request(path, principal, observation, phase), timeout=a.timeout)
            except asyncio.CancelledError:
                raise
            except Exception:
                observation['failure'] = observation['failure'] or 'INVALID_OR_TRANSPORT'
                body = None  # Never propagate response or transport exception text.
            if phase == 0:
                p = self.ps[principal]
                identities[principal] = body is not None and body.get('username') == p.username and body.get('role') == p.role
                continue
            m = next(m for m in self.mappings if m.case_id == case_id)
            c = self.manifest.require_case(case_id)
            if phase == 1:
                valid = (body is not None and identities.get(principal) is True
                         and _get(body, m.object_path) == m.object_value
                         and _get(body, m.owner_path) == self.ps[principal].username
                         and all(_present(_get(body, p)) for p in m.sensitive_paths))
                baselines[case_id] = body if valid else None
                continue
            valid = body is not None and identities.get(principal) is True
            conclusion = 'INCONCLUSIVE'
            if m.owner_principal:
                baseline = baselines.get(case_id)
                valid = valid and baseline is not None
                if valid:
                    # Typed canonical JSON preserves array order and ignores no dynamic fields.
                    observation['wholebody_equal'] = _digest(body) == _digest(baseline)
                    match = (_get(body, m.object_path) == m.object_value
                             and _get(body, m.owner_path) == self.ps[m.owner_principal].username
                             and all(_present(_get(body, p)) and type(_get(body, p)) is type(_get(baseline, p)) and _get(body, p) == _get(baseline, p) for p in m.sensitive_paths))
                    conclusion = 'CONFIRMED' if match and c.expected_decision == 'DENY' else 'INCONCLUSIVE'
                    observation['confidence'] = 'POLICY_AND_DISCLOSURE' if conclusion == 'CONFIRMED' else 'INSUFFICIENT'
            elif path == '/me':
                valid = valid and body.get('username') == self.ps[principal].username and body.get('role') == self.ps[principal].role
            results[case_id] = (valid, conclusion)
        observations, artifacts, evidence = [], {}, []
        for c in self.manifest.cases:
            valid, conclusion = results.get(c.case_id, (False, 'INCONCLUSIVE'))
            status = 'COMPLETED' if valid else ('INVALID' if c.case_id in results else 'NOT_RUN')
            signal = 'ACCESS_ALLOWED' if valid else 'UNKNOWN'
            receipt = dict(schema_version=1, kind='OBSERVATION', manifest_digest=self.manifest.content_digest,
                           manifest_version=self.manifest.version, case_id=c.case_id, method='T18',
                           execution_id=a.execution_id, execution_status=status, signal=signal)
            raw = json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode()
            ref = 'artifact-' + hashlib.sha256(raw).hexdigest()[:32]
            artifacts[ref] = raw
            provenance = Provenance(ref, hashlib.sha256(raw).hexdigest(), 'AUTOMATED_VERIFIER', 'cmp07-r1', None)
            observations.append(Observation('T18', self.manifest.content_digest, self.manifest.version,
                                c, a.execution_id, status, signal, provenance).to_dict())
            evidence.append(dict(case_id=c.case_id, conclusion=conclusion,
                                 reason=stop if status == 'NOT_RUN' else ('VALIDATED' if valid else 'INVALID_TEST'),
                                 source_hash=a.source_hash, timing=None, timing_status='UNKNOWN',
                                 body_observation=body_observations.get(c.case_id)))
        envelope = import_bundle(dict(schema_version=1, manifest=self.manifest.to_dict(), observations=observations,
                                selections=[dict(method='T18', execution_id=a.execution_id)], legacy=[]), artifacts)
        result = dict(envelope=envelope, evidence=evidence, counts=tuple(self.counts), stop=stop,
                      mapping_digest=a.mapping_digest, principal_digest=a.principal_digest, source_hash=a.source_hash,
                      manifest_digest=self.manifest.content_digest, execution_id=a.execution_id)
        return result | {'content_digest': _digest(result)}
