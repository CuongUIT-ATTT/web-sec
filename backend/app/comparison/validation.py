"""Backend-owned bounded receipt validation; no CLI imports or attestation."""
import base64
import binascii
import hashlib
import json
from collections.abc import Mapping

from .case_manifest import CaseManifest, _digest
from .observations import (ObservationSet, LegacyUnlinked, Provenance,
                           adapt_observation, _exact, _opaque, _match, _HASH)
from .observations import METHODS
from dataclasses import dataclass

@dataclass(frozen=True)
class Selection:
    method: str
    execution_id: str

    def __post_init__(self):
        if type(self.method) is not str or self.method not in METHODS:
            raise ValueError("Invalid method")
        _opaque(self.execution_id, "execution")

MAX_BUNDLE_BYTES = 2_000_000
MAX_ARTIFACT_BYTES = 4096
MAX_ARTIFACT_TOTAL_BYTES = 2_000_000
MAX_ITEMS = 1000
MAX_DEPTH = 12


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _bounded(value, depth=0):
    if depth > MAX_DEPTH:
        raise ValueError('Schema nesting limit')
    if type(value) is dict:
        if len(value) > MAX_ITEMS or any(type(k) is not str for k in value):
            raise ValueError('Invalid JSON object')
        for child in value.values():
            _bounded(child, depth + 1)
    elif type(value) is list:
        if len(value) > MAX_ITEMS:
            raise ValueError('Item limit')
        for child in value:
            _bounded(child, depth + 1)
    elif type(value) is str:
        if len(value) > 512:
            raise ValueError('String limit')
    elif value is not None and type(value) not in (bool, int):
        raise ValueError('Invalid JSON scalar')
    elif type(value) is int and abs(value) > 2**53:
        raise ValueError('Integer limit')


def _json(value, limit):
    try:
        if type(value) is bytes:
            if len(value) > limit:
                raise ValueError('Byte limit')
            value = json.loads(value.decode('utf-8'), object_pairs_hook=_pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid constant')))
        elif isinstance(value, Mapping):
            value = dict(value)
        else:
            raise ValueError('Explicit bytes or mapping required')
        _bounded(value)
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        if len(encoded.encode('ascii')) > limit:
            raise ValueError('Byte limit')
        return json.loads(encoded)
    except (TypeError, UnicodeError, RecursionError, OverflowError):
        raise ValueError('Malformed sanitized JSON') from None


def _schema(value, names):
    _exact(value, names)
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported schema')


def validate_dto(raw):
    """Validate detached schema 1/2 DTO, including exact receipt byte bindings."""
    data = _json(raw, MAX_BUNDLE_BYTES)
    _exact(data, ('schema_version', 'manifest', 'observations', 'selections', 'legacy',
                   'artifacts', 'attestation_status', 'content_digest'))
    if type(data['schema_version']) is not int or data['schema_version'] not in (1, 2):
        raise ValueError('Unsupported schema')
    version = data['schema_version']
    supplied = data.pop('content_digest')
    _match(_HASH, supplied)
    if _digest(data) != supplied or data['attestation_status'] != 'UNVERIFIED':
        raise ValueError('Digest or attestation mismatch')
    manifest = CaseManifest.from_dict(data['manifest'])
    for key in ('observations', 'selections', 'legacy', 'artifacts'):
        if type(data[key]) is not list:
            raise ValueError('Array required')
    observations = ObservationSet.build(manifest, (
        adapt_observation(manifest, item, method=item.get('method'))
        if type(item) is dict else (_ for _ in ()).throw(ValueError('Invalid observation'))
        for item in data['observations']))
    selections = []
    for item in data['selections']:
        _exact(item, ('method', 'execution_id'))
        selections.append(Selection(**item))
    if not selections or len({s.method for s in selections}) != len(selections):
        raise ValueError('Invalid selections')
    expected = {}
    def require(provenance, binding):
        if provenance is None:
            return
        ref = provenance.artifact_ref
        entry = (provenance.artifact_hash, binding)
        if ref in expected and expected[ref] != entry:
            raise ValueError('Conflicting artifact binding')
        expected[ref] = entry
    for obs in observations.observations:
        require(obs.provenance, dict(schema_version=1, kind='OBSERVATION',
            manifest_digest=obs.manifest_digest, manifest_version=obs.manifest_version,
            case_id=obs.case_id, method=obs.method, execution_id=obs.execution_id,
            execution_status=obs.execution_status, signal=obs.signal))
    seen = set()
    for item in data['legacy']:
        _exact(item, ('method', 'source_alias', 'provenance', 'linkage_status', 'conclusion'))
        entry = LegacyUnlinked(item['method'], item['source_alias'],
            None if item['provenance'] is None else Provenance.from_dict(item['provenance']))
        key = (entry.method, entry.source_alias)
        if key in seen or item['linkage_status'] != 'UNLINKED' or item['conclusion'] != 'UNKNOWN':
            raise ValueError('Invalid legacy inventory')
        seen.add(key)
        require(entry.provenance, dict(schema_version=1, kind='LEGACY_INVENTORY',
            method=entry.method, source_alias=entry.source_alias, linkage_status='UNLINKED'))
    if version == 1 and (expected or data['artifacts']):
        raise ValueError('Receipt binding unavailable in serialized schema 1')
    catalog = set()
    total = 0
    for item in data['artifacts']:
        _exact(item, ('artifact_ref', 'artifact_hash', 'size_bytes', 'integrity_status',
                      'attestation_status', 'receipt_encoding', 'receipt_base64_chunks'))
        ref = item['artifact_ref']
        _opaque(ref, 'artifact')
        _match(_HASH, item['artifact_hash'])
        if ref in catalog or ref not in expected or expected[ref][0] != item['artifact_hash']:
            raise ValueError('Catalog mismatch')
        if type(item['size_bytes']) is not int or not 1 <= item['size_bytes'] <= MAX_ARTIFACT_BYTES:
            raise ValueError('Artifact size limit')
        total += item['size_bytes']
        if total > MAX_ARTIFACT_TOTAL_BYTES:
            raise ValueError('Artifact total limit')
        if item['integrity_status'] != 'HASH_MATCHED' or item['attestation_status'] != 'UNVERIFIED':
            raise ValueError('Invalid catalog status')
        chunks = item['receipt_base64_chunks']
        if (item['receipt_encoding'] != 'base64' or type(chunks) is not list
                or not 1 <= len(chunks) <= 11
                or any(type(c) is not str or not 1 <= len(c) <= 512 for c in chunks)
                or any(len(c) != 512 for c in chunks[:-1])):
            raise ValueError('Invalid receipt encoding')
        encoded = ''.join(chunks)
        if len(encoded) > 5464:
            raise ValueError('Encoded receipt limit')
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError('Invalid receipt encoding') from None
        if base64.b64encode(content).decode('ascii') != encoded:
            raise ValueError('Noncanonical receipt encoding')
        if len(content) != item['size_bytes']:
            raise ValueError('Receipt size mismatch')
        if hashlib.sha256(content).hexdigest() != item['artifact_hash']:
            raise ValueError('Receipt hash mismatch')
        receipt = _json(content, MAX_ARTIFACT_BYTES)
        _schema(receipt, expected[ref][1])
        if receipt != expected[ref][1]:
            raise ValueError('Receipt binding mismatch')
        catalog.add(ref)
    if catalog != set(expected):
        raise ValueError('Catalog membership mismatch')
    if data['manifest'] != manifest.to_dict() or data['observations'] != [o.to_dict() for o in observations.observations]:
        raise ValueError('Noncanonical contract')
    if data['selections'] != sorted(data['selections'], key=lambda s: s['method']):
        raise ValueError('Noncanonical selections')
    if data['legacy'] != sorted(data['legacy'], key=lambda e: (e['method'], e['source_alias'])):
        raise ValueError('Noncanonical legacy')
    if data['artifacts'] != sorted(data['artifacts'], key=lambda e: e['artifact_ref']):
        raise ValueError('Noncanonical catalog')
    return data | {'content_digest': supplied}
