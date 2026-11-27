"""Pure CMP-03 contracts. Structural provenance is not attestation or ground truth.

Only opaque catalog references are accepted; resolving/hashing artifacts belongs
upstream. No I/O, historical mapping, metrics or execution occurs here.
"""
from collections.abc import Mapping, Iterable
from dataclasses import dataclass, asdict
import re

from .case_manifest import CaseDefinition, CaseManifest, _digest

_HASH = re.compile(r'[0-9a-f]{64}\Z')
_OPAQUE = re.compile(r'(?:execution|artifact|operator|source)-[0-9a-f]{32}\Z')
_LABEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')
METHODS = frozenset({'MANUAL', 'T18', 'ZAP'})
STATUSES = frozenset({'COMPLETED', 'NOT_RUN', 'INVALID', 'UNKNOWN', 'BLOCKED'})
SIGNALS = frozenset({'ACCESS_ALLOWED', 'ACCESS_DENIED', 'UNKNOWN', 'ILLEGAL', 'LEGAL'})


def _exact(value, names):
    if not isinstance(value, Mapping) or set(value) != set(names):
        raise ValueError('Invalid fields')


def _match(pattern, value):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError('Invalid symbolic value')


def _opaque(value, prefix):
    _match(_OPAQUE, value)
    if not value.startswith(prefix + '-'):
        raise ValueError('Invalid alias namespace')


@dataclass(frozen=True, slots=True)
class Provenance:
    artifact_ref: str
    artifact_hash: str
    producer_kind: str
    producer_version: str
    operator_alias: str | None

    def __post_init__(self):
        _opaque(self.artifact_ref, 'artifact')
        _match(_HASH, self.artifact_hash)
        _match(_LABEL, self.producer_version)
        if self.producer_kind not in ('HUMAN', 'AUTOMATED_VERIFIER', 'ZAP'):
            raise ValueError('Invalid producer kind')
        if self.operator_alias is not None:
            _opaque(self.operator_alias, 'operator')
        if self.producer_kind == 'HUMAN' and self.operator_alias is None:
            raise ValueError('Human provenance requires operator alias')

    @classmethod
    def from_dict(cls, value):
        _exact(value, cls.__dataclass_fields__)
        return cls(**value)


@dataclass(frozen=True, slots=True)
class Observation:
    method: str
    manifest_digest: str
    manifest_version: str
    case_revision: CaseDefinition
    execution_id: str
    execution_status: str
    signal: str
    provenance: Provenance | None

    def __post_init__(self):
        if not isinstance(self.method, str) or self.method not in METHODS:
            raise ValueError('Invalid observation method')
        _match(_HASH, self.manifest_digest)
        if self.manifest_version != 'sha256:' + self.manifest_digest:
            raise ValueError('Invalid manifest version')
        if type(self.case_revision) is not CaseDefinition:
            raise ValueError('Invalid case revision')
        _opaque(self.execution_id, 'execution')
        if not isinstance(self.execution_status, str) or self.execution_status not in STATUSES:
            raise ValueError('Invalid execution status')
        if not isinstance(self.signal, str) or self.signal not in SIGNALS:
            raise ValueError('Invalid signal')
        if self.execution_status != 'COMPLETED' and self.signal != 'UNKNOWN':
            raise ValueError('Unexecuted/invalid observations cannot decide access')
        if self.signal in ('ILLEGAL', 'LEGAL') and self.method != 'ZAP':
            raise ValueError('ZAP-only access-rule signal')
        if self.provenance is not None:
            if type(self.provenance) is not Provenance:
                raise ValueError('Invalid provenance')
            allowed = {'MANUAL': {'HUMAN', 'AUTOMATED_VERIFIER'},
                       'T18': {'AUTOMATED_VERIFIER'}, 'ZAP': {'ZAP'}}
            if self.provenance.producer_kind not in allowed[self.method]:
                raise ValueError('Producer/method mismatch')

    @property
    def case_id(self):
        return self.case_revision.case_id

    @property
    def provenance_status(self):
        # Means structurally complete source metadata, never human attestation.
        return 'SOURCE_RECORDED' if self.provenance is not None else 'UNVERIFIED'

    @property
    def human_observation_verified(self):
        return (self.method == 'MANUAL' and self.execution_status == 'COMPLETED'
                and self.provenance is not None and self.provenance.producer_kind == 'HUMAN')

    @property
    def conclusion(self):
        # No adapter establishes BOLA/protected-field equivalence or negatives.
        if self.execution_status == 'COMPLETED' and self.provenance is not None:
            if self.signal in ('ACCESS_ALLOWED', 'ACCESS_DENIED'):
                return self.signal
        return 'UNKNOWN'

    def to_dict(self):
        return dict(method=self.method, manifest_digest=self.manifest_digest,
                    manifest_version=self.manifest_version, case_revision=self.case_revision.to_dict(),
                    execution_id=self.execution_id, execution_status=self.execution_status,
                    signal=self.signal, provenance=asdict(self.provenance) if self.provenance else None)

    @property
    def content_digest(self):
        return _digest(self.to_dict())


def adapt_observation(manifest: CaseManifest, payload: Mapping, *, method: str) -> Observation:
    """Explicit linked import; never infer membership from paths or legacy IDs."""
    if type(manifest) is not CaseManifest:
        raise ValueError('Manifest required')
    _exact(payload, Observation.__dataclass_fields__)
    if payload['method'] != method:
        raise ValueError('Adapter method mismatch')
    if payload['manifest_digest'] != manifest.content_digest or payload['manifest_version'] != manifest.version:
        raise ValueError('Cohort mismatch')
    case = CaseDefinition.from_dict(payload['case_revision'])
    if manifest.require_case(case.case_id) != case:
        raise ValueError('Case revision mismatch')
    provenance = payload['provenance']
    return Observation(**(dict(payload) | {'case_revision': case, 'provenance':
        None if provenance is None else Provenance.from_dict(provenance)}))


def adapt_manual(manifest, payload):
    return adapt_observation(manifest, payload, method='MANUAL')


def adapt_t18(manifest, payload):
    return adapt_observation(manifest, payload, method='T18')


def adapt_zap(manifest, payload):
    return adapt_observation(manifest, payload, method='ZAP')


@dataclass(frozen=True, slots=True)
class ObservationSet:
    manifest: CaseManifest
    observations: tuple[Observation, ...]

    def __post_init__(self):
        if type(self.manifest) is not CaseManifest or type(self.observations) is not tuple:
            raise ValueError('Immutable cohort and observations required')
        seen = set()
        for item in self.observations:
            if type(item) is not Observation:
                raise ValueError('Invalid observation')
            adapt_observation(self.manifest, item.to_dict(), method=item.method)
            # One observation per execution, case and method. Repeats require new execution IDs.
            key = (item.method, item.execution_id, item.case_id)
            if key in seen:
                raise ValueError('Duplicate observation')
            seen.add(key)
        object.__setattr__(self, 'observations', tuple(sorted(self.observations,
                           key=lambda o: (o.method, o.execution_id, o.case_id))))

    @classmethod
    def build(cls, manifest, observations: Iterable[Observation]):
        return cls(manifest, tuple(observations))


@dataclass(frozen=True, slots=True)
class LegacyUnlinked:
    """Source inventory only: intentionally has no case/cohort/run mapping."""
    method: str
    source_alias: str
    provenance: Provenance | None

    def __post_init__(self):
        if not isinstance(self.method, str) or self.method not in METHODS:
            raise ValueError('Invalid method')
        _opaque(self.source_alias, 'source')
        if self.provenance is not None and type(self.provenance) is not Provenance:
            raise ValueError('Invalid provenance')

    @property
    def linkage_status(self):
        return 'UNLINKED'

    @property
    def conclusion(self):
        return 'UNKNOWN'
