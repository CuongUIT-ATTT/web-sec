"""CMP05-A pure sanitized import. Byte integrity is never source attestation.

Schema-1 redacted receipts are carried byte-exact in schema-2 envelopes.
Explicit schema-1 export is retained for offline compatibility only.
No paths, I/O, history lookup, review claims, predictions or execution.
"""
import base64
import binascii
import hashlib
import json
from collections.abc import Mapping

from .case_manifest import CaseManifest, _digest
from .observations import (ObservationSet, LegacyUnlinked, Provenance,
                           adapt_observation, _exact, _opaque, _match, _HASH)
from .metrics import Selection

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


def import_bundle(bundle, artifact_bytes, *, output_schema_version=2):
    """Return detached JSON DTO from caller data and opaque-ref -> bytes catalog.

    Artifact digest covers exact supplied bytes (not reserialized JSON). Catalog
    must contain exactly referenced artifacts. Hash checks do not authenticate
    operators, reviews, executions or protected fields. Caller must separately
    authorize project scope before persistence; this function has no user context.
    """
    if type(output_schema_version) is not int or output_schema_version not in (1, 2):
        raise ValueError('Unsupported envelope schema')
    data = _json(bundle, MAX_BUNDLE_BYTES)
    _schema(data, ('schema_version', 'manifest', 'observations', 'selections', 'legacy'))
    for key in ('observations', 'selections', 'legacy'):
        if type(data[key]) is not list:
            raise ValueError('Array required')
    if not isinstance(artifact_bytes, Mapping) or len(artifact_bytes) > MAX_ITEMS:
        raise ValueError('Explicit bounded catalog required')
    manifest = CaseManifest.from_dict(data['manifest'])
    observations = ObservationSet.build(manifest, (
        adapt_observation(manifest, item, method=item.get('method'))
        if isinstance(item, dict) else (_ for _ in ()).throw(ValueError('Invalid observation'))
        for item in data['observations']))
    selections = []
    for item in data['selections']:
        _exact(item, ('method', 'execution_id'))
        selections.append(Selection(**item))
    if not selections or len({s.method for s in selections}) != len(selections):
        raise ValueError('Explicit unique method selection required')
    # Selection may intentionally have no observations: downstream reports NOT_RUN.
    legacy = []
    for item in data['legacy']:
        _exact(item, ('method', 'source_alias', 'provenance'))
        entry = LegacyUnlinked(item['method'], item['source_alias'],
            None if item['provenance'] is None else Provenance.from_dict(item['provenance']))
        if (entry.method, entry.source_alias) in {(e.method, e.source_alias) for e in legacy}:
            raise ValueError('Duplicate legacy source')
        legacy.append(entry)
    expected = {}
    hashes = {}

    def require(provenance, receipt):
        if provenance is None:
            return
        ref = provenance.artifact_ref
        if ref in expected and (expected[ref] != receipt or hashes[ref] != provenance.artifact_hash):
            raise ValueError('Conflicting artifact binding')
        expected[ref], hashes[ref] = receipt, provenance.artifact_hash

    for obs in observations.observations:
        require(obs.provenance, dict(schema_version=1, kind='OBSERVATION',
            manifest_digest=manifest.content_digest, manifest_version=manifest.version,
            case_id=obs.case_id, method=obs.method, execution_id=obs.execution_id,
            execution_status=obs.execution_status, signal=obs.signal))
    for entry in legacy:
        require(entry.provenance, dict(schema_version=1, kind='LEGACY_INVENTORY',
            method=entry.method, source_alias=entry.source_alias, linkage_status='UNLINKED'))
    if set(artifact_bytes) != set(expected):
        raise ValueError('Missing or unreferenced artifact')
    total = 0
    catalog = []
    for ref in sorted(expected):
        _opaque(ref, 'artifact')
        _match(_HASH, hashes[ref])
        content = artifact_bytes[ref]
        if type(content) is not bytes or len(content) > MAX_ARTIFACT_BYTES:
            raise ValueError('Bounded artifact bytes required')
        total += len(content)
        if total > MAX_ARTIFACT_TOTAL_BYTES:
            raise ValueError('Artifact total byte limit')
        digest = hashlib.sha256(content).hexdigest()
        if digest != hashes[ref]:
            raise ValueError('Artifact hash mismatch')
        receipt = _json(content, MAX_ARTIFACT_BYTES)
        _schema(receipt, expected[ref])
        if receipt != expected[ref]:
            raise ValueError('Artifact schema or identity mismatch')
        entry = dict(artifact_ref=ref, artifact_hash=digest, size_bytes=len(content),
                     integrity_status='HASH_MATCHED', attestation_status='UNVERIFIED')
        if output_schema_version == 2:
            encoded = base64.b64encode(content).decode('ascii')
            entry.update(receipt_encoding='base64',
                         receipt_base64_chunks=[encoded[i:i+512] for i in range(0, len(encoded), 512)])
        catalog.append(entry)
    result = dict(schema_version=output_schema_version, manifest=manifest.to_dict(),
        observations=[o.to_dict() for o in observations.observations],
        selections=[dict(method=s.method, execution_id=s.execution_id)
                    for s in sorted(selections, key=lambda s: s.method)],
        legacy=[dict(method=e.method, source_alias=e.source_alias,
                     provenance=None if e.provenance is None else dict(
                         artifact_ref=e.provenance.artifact_ref, artifact_hash=e.provenance.artifact_hash,
                         producer_kind=e.provenance.producer_kind, producer_version=e.provenance.producer_version,
                         operator_alias=e.provenance.operator_alias),
                     linkage_status='UNLINKED', conclusion='UNKNOWN')
                for e in sorted(legacy, key=lambda e: (e.method, e.source_alias))],
        artifacts=catalog, attestation_status='UNVERIFIED')
    return _json(result | {'content_digest': _digest(result)}, MAX_BUNDLE_BYTES)


def validate_envelope(raw):
    """Pure downstream reference algorithm; backend must own its implementation.

    Schema 1 without provenance remains accepted. Its opaque catalog cannot prove
    receipt binding, so schema 1 with any provenance fails closed. Never strip
    provenance to migrate a bundle. Schema 2 verifies exact original bytes, then
    reuses full import validation and compares the complete canonical DTO.
    """
    data = _json(raw, MAX_BUNDLE_BYTES)
    _exact(data, ('schema_version', 'manifest', 'observations', 'selections',
                  'legacy', 'artifacts', 'attestation_status', 'content_digest'))
    version = data['schema_version']
    if type(version) is not int or version not in (1, 2):
        raise ValueError('Unsupported envelope schema')
    supplied = data.pop('content_digest')
    _match(_HASH, supplied)
    if _digest(data) != supplied or data['attestation_status'] != 'UNVERIFIED':
        raise ValueError('Digest or attestation mismatch')
    for key in ('observations', 'selections', 'legacy', 'artifacts'):
        if type(data[key]) is not list:
            raise ValueError('Array required')
    catalog = {}
    total = 0
    for entry in data['artifacts']:
        if version == 1:
            raise ValueError('Receipt binding unavailable in serialized schema 1')
        _exact(entry, ('artifact_ref', 'artifact_hash', 'size_bytes', 'integrity_status',
                       'attestation_status', 'receipt_encoding', 'receipt_base64_chunks'))
        ref = entry['artifact_ref']
        _opaque(ref, 'artifact')
        if ref in catalog:
            raise ValueError('Duplicate artifact')
        chunks = entry['receipt_base64_chunks']
        if (entry['receipt_encoding'] != 'base64' or type(chunks) is not list
                or not 1 <= len(chunks) <= 11
                or any(type(c) is not str or not 1 <= len(c) <= 512 for c in chunks)
                or any(len(c) != 512 for c in chunks[:-1])):
            raise ValueError('Invalid receipt encoding')
        encoded = ''.join(chunks)
        if len(encoded) > 4 * ((MAX_ARTIFACT_BYTES + 2) // 3):
            raise ValueError('Encoded receipt limit')
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError('Invalid receipt encoding') from None
        if base64.b64encode(content).decode('ascii') != encoded:
            raise ValueError('Noncanonical receipt encoding')
        if not 1 <= len(content) <= MAX_ARTIFACT_BYTES:
            raise ValueError('Artifact size limit')
        total += len(content)
        if total > MAX_ARTIFACT_TOTAL_BYTES:
            raise ValueError('Artifact total byte limit')
        if type(entry['size_bytes']) is not int or entry['size_bytes'] != len(content):
            raise ValueError('Artifact size mismatch')
        catalog[ref] = content
    legacy = []
    for entry in data['legacy']:
        _exact(entry, ('method', 'source_alias', 'provenance', 'linkage_status', 'conclusion'))
        legacy.append({k: entry[k] for k in ('method', 'source_alias', 'provenance')})
    source = dict(schema_version=1, manifest=data['manifest'],
                  observations=data['observations'], selections=data['selections'], legacy=legacy)
    rebuilt = import_bundle(source, catalog, output_schema_version=version)
    if rebuilt != data | {'content_digest': supplied}:
        raise ValueError('Noncanonical or inconsistent envelope')
    return rebuilt
