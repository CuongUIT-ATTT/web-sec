"""Pure, immutable comparison cohort contract; no execution or historical joins.

Aliases and static operation templates must be assigned/reviewed upstream. Never
supply credentials, rendered resource paths, usernames or resource identifiers.
Digests establish content identity, not reviewed ground truth or execution proof.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import json
import re
from collections.abc import Mapping, Iterable

SCHEMA_VERSION = 1
METHODS = frozenset({'GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE'})
OWNER_CATEGORIES = frozenset({'SELF', 'OTHER', 'PUBLIC', 'NONE'})
DECISIONS = frozenset({'ALLOW', 'DENY'})
_TOKEN = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')
_VERSION = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')
_ALIAS = re.compile(r'(?:actor|owner)-[0-9a-f]{32}\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_TEMPLATE = re.compile(r'/(?:[A-Za-z][A-Za-z0-9_-]*|\{[A-Za-z][A-Za-z0-9_]*\})(?:/(?:[A-Za-z][A-Za-z0-9_-]*|\{[A-Za-z][A-Za-z0-9_]*\}))*\Z')


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')).hexdigest()


def _match(pattern: re.Pattern, value: object, field: str) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f'Invalid {field}')


@dataclass(frozen=True, slots=True)
class CaseDefinition:
    method: str
    operation_template: str
    actor_alias: str
    actor_role: str
    owner_alias: str | None
    owner_category: str
    fixture_version: str
    fixture_hash: str
    policy_id: str
    policy_version: str
    expected_decision: str

    def __post_init__(self) -> None:
        for name, allowed in (('method', METHODS), ('owner_category', OWNER_CATEGORIES), ('expected_decision', DECISIONS)):
            value = getattr(self, name)
            if not isinstance(value, str) or value not in allowed:
                raise ValueError(f'Invalid {name}')
        if self.operation_template != '/':
            _match(_TEMPLATE, self.operation_template, 'operation_template')
        _match(_ALIAS, self.actor_alias, 'actor_alias')
        if not self.actor_alias.startswith('actor-'):
            raise ValueError('Invalid actor_alias')
        for name in ('actor_role', 'policy_id'):
            _match(_TOKEN, getattr(self, name), name)
        for name in ('fixture_version', 'policy_version'):
            _match(_VERSION, getattr(self, name), name)
        _match(_HASH, self.fixture_hash, 'fixture_hash')
        if self.owner_category in {'SELF', 'OTHER'}:
            _match(_ALIAS, self.owner_alias, 'owner_alias')
            if not self.owner_alias.startswith('owner-'):
                raise ValueError('Invalid owner_alias')
        elif self.owner_alias is not None:
            raise ValueError('Unowned cases require null owner_alias')

    @property
    def case_id(self) -> str:
        """Opaque content address; semantic edits intentionally produce a new ID."""
        return 'case-' + _digest(asdict(self))

    def to_dict(self) -> dict:
        return {'case_id': self.case_id, **asdict(self)}

    @classmethod
    def from_dict(cls, value: Mapping) -> CaseDefinition:
        names = {f.name for f in fields(cls)}
        if not isinstance(value, Mapping) or set(value) != names | {'case_id'}:
            raise ValueError('Invalid case fields')
        case = cls(**{name: value[name] for name in names})
        if value['case_id'] != case.case_id:
            raise ValueError('Case digest mismatch')
        return case


@dataclass(frozen=True, slots=True)
class CaseManifest:
    cases: tuple[CaseDefinition, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.cases, tuple) or not self.cases or any(type(c) is not CaseDefinition for c in self.cases):
            raise ValueError('Nonempty immutable cases required')
        ordered = tuple(sorted(self.cases, key=lambda c: c.case_id))
        if len({c.case_id for c in ordered}) != len(ordered):
            raise ValueError('Duplicate case')
        # One expected decision/fixture/policy revision per scenario in a cohort.
        keys = [(c.method, c.operation_template, c.actor_alias, c.actor_role, c.owner_alias, c.owner_category) for c in ordered]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate scenario')
        object.__setattr__(self, 'cases', ordered)

    @classmethod
    def build(cls, cases: Iterable[CaseDefinition]) -> CaseManifest:
        return cls(tuple(cases))

    @property
    def content_digest(self) -> str:
        return _digest({'schema_version': SCHEMA_VERSION, 'cases': [c.to_dict() for c in self.cases]})

    @property
    def version(self) -> str:
        return 'sha256:' + self.content_digest

    def to_dict(self) -> dict:
        return {'schema_version': SCHEMA_VERSION, 'version': self.version, 'content_digest': self.content_digest, 'cases': [c.to_dict() for c in self.cases]}

    @classmethod
    def from_dict(cls, value: Mapping) -> CaseManifest:
        if not isinstance(value, Mapping) or set(value) != {'schema_version', 'version', 'content_digest', 'cases'}:
            raise ValueError('Invalid manifest fields')
        if type(value['schema_version']) is not int or value['schema_version'] != SCHEMA_VERSION or not isinstance(value['cases'], list):
            raise ValueError('Unsupported manifest schema')
        manifest = cls.build(CaseDefinition.from_dict(c) for c in value['cases'])
        if value['content_digest'] != manifest.content_digest or value['version'] != manifest.version:
            raise ValueError('Manifest digest mismatch')
        return manifest

    def require_case(self, case_id: str) -> CaseDefinition:
        for case in self.cases:
            if case.case_id == case_id:
                return case
        raise ValueError('Unknown case ID')
