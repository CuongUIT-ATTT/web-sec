"""Synthetic redacted receipts only; no real execution or attestation."""
from copy import deepcopy
import base64
import hashlib
import json
import unittest
from unittest.mock import patch

from authz_lab.evaluation.case_manifest import CaseManifest
from authz_lab.evaluation.importer import import_bundle, validate_envelope
from authz_lab.evaluation.case_manifest import _digest
from authz_lab.evaluation.observations import ObservationSet, adapt_observation
from authz_lab.evaluation.metrics import evaluate, Selection
from .test_observations import case, payload


def fixture():
    manifest = CaseManifest.build([case(), case('2')])
    observations, catalog = [], {}
    for index, c in enumerate(manifest.cases):
        obs = payload(manifest, c)
        ref = 'artifact-' + str(index) * 32
        receipt = dict(schema_version=1, kind='OBSERVATION',
            manifest_digest=manifest.content_digest, manifest_version=manifest.version,
            case_id=c.case_id, method=obs['method'], execution_id=obs['execution_id'],
            execution_status=obs['execution_status'], signal=obs['signal'])
        content = json.dumps(receipt).encode()
        obs['provenance'].update(artifact_ref=ref, artifact_hash=hashlib.sha256(content).hexdigest())
        observations.append(obs)
        catalog[ref] = content
    return dict(schema_version=1, manifest=manifest.to_dict(), observations=observations,
                selections=[dict(method='MANUAL', execution_id=observations[0]['execution_id'])], legacy=[]), catalog


class ImporterTests(unittest.TestCase):
    def test_roundtrip_deterministic_detached_no_attestation(self):
        data, catalog = fixture()
        before = deepcopy(data)
        result = import_bundle(data, catalog)
        self.assertEqual(result, import_bundle(json.dumps(data).encode(), catalog))
        data['observations'].reverse()
        self.assertEqual(result, import_bundle(data, dict(reversed(list(catalog.items())))))
        self.assertEqual(result['attestation_status'], 'UNVERIFIED')
        self.assertEqual({a['integrity_status'] for a in result['artifacts']}, {'HASH_MATCHED'})
        result['observations'][0]['signal'] = 'UNKNOWN'
        self.assertEqual(before['observations'][0]['signal'], 'ACCESS_DENIED')

    def test_metrics_remain_excluded_without_separate_review(self):
        data, catalog = fixture()
        result = import_bundle(data, catalog)
        manifest = CaseManifest.from_dict(result['manifest'])
        observations = ObservationSet.build(manifest, [adapt_observation(manifest, o, method=o['method']) for o in result['observations']])
        score = evaluate(observations, [], [], [Selection(**s) for s in result['selections']])
        self.assertEqual({r.exclusion_reason for r in score.rows}, {'UNREVIEWED_TRUTH'})
        self.assertEqual(score.summary()[0]['eligible_count'], 0)

    def test_no_source_and_empty_selected_execution(self):
        data, _ = fixture()
        data['observations'] = []
        result = import_bundle(data, {})
        self.assertEqual(result['artifacts'], [])
        data, _ = fixture()
        for o in data['observations']:
            o['provenance'] = None
        self.assertEqual(import_bundle(data, {})['artifacts'], [])

    def test_legacy_stays_unlinked(self):
        data, catalog = fixture()
        data['legacy'] = [dict(method='ZAP', source_alias='source-'+'9'*32, provenance=None)]
        result = import_bundle(data, catalog)
        self.assertEqual(result['legacy'][0]['linkage_status'], 'UNLINKED')
        self.assertNotIn('case_id', result['legacy'][0])
        data['legacy'] *= 2
        with self.assertRaises(ValueError):
            import_bundle(data, catalog)

    def test_duplicates_unknown_missing_and_revision_rejected(self):
        base, catalog = fixture()
        mutations = [lambda d: d['observations'].append(deepcopy(d['observations'][0])),
                     lambda d: d['selections'].append(deepcopy(d['selections'][0])),
                     lambda d: d.update(extra='secret-canary'),
                     lambda d: d.update(schema_version=True),
                     lambda d: d.update(selections=[]),
                     lambda d: d['observations'][0]['case_revision'].update(policy_version='v2'),
                     lambda d: d['manifest'].update(version='sha256:'+'0'*64),
                     lambda d: d['manifest']['cases'].pop(),
                     lambda d: d['observations'][0].update(execution_id='execution-'+'8'*32),
                     lambda d: d['observations'][0].update(manifest_digest='0'*64)]
        for mutation in mutations:
            data = deepcopy(base)
            mutation(data)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                import_bundle(data, catalog)
        for key in base:
            data = deepcopy(base)
            del data[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                import_bundle(data, catalog)

    def test_hash_catalog_and_schema_tampering(self):
        data, catalog = fixture()
        ref = next(iter(catalog))
        for content in (catalog[ref]+b' ', b'{}', b'Bearer secret-canary', '/tmp/secret', None):
            with self.subTest(content=type(content)), self.assertRaises(ValueError):
                import_bundle(data, catalog | {ref: content})
        for content in (dict(json.loads(catalog[ref]), schema_version=True),
                        dict(json.loads(catalog[ref]), body='secret-canary'),
                        dict(json.loads(catalog[ref]), case_id='case-'+'0'*64)):
            raw = json.dumps(content).encode()
            changed = deepcopy(data)
            changed['observations'][0]['provenance']['artifact_hash'] = hashlib.sha256(raw).hexdigest()
            with self.subTest(content=content), self.assertRaises(ValueError):
                import_bundle(changed, catalog | {ref: raw})
        for wrong in ({}, catalog | {'/tmp/secret': b'{}'}):
            with self.subTest(catalog=wrong.keys()), self.assertRaises(ValueError):
                import_bundle(data, wrong)

    def test_malformed_size_depth_limits(self):
        data, catalog = fixture()
        for value in (b'{"schema_version":1,"schema_version":1}', b'NaN', b'\xff',
                      b'{', b'[]', b' '*2_000_001, [], None, {'x': 1.5}, {'x': float('nan')}):
            with self.subTest(value=type(value)), self.assertRaises(ValueError):
                import_bundle(value, catalog)
        with patch('authz_lab.evaluation.importer.MAX_ARTIFACT_BYTES', 10), self.assertRaises(ValueError):
            import_bundle(data, catalog)
        with patch('authz_lab.evaluation.importer.MAX_ARTIFACT_TOTAL_BYTES', 10), self.assertRaises(ValueError):
            import_bundle(data, catalog)
        nested = {}
        for _ in range(15):
            nested = {'x': nested}
        for value in (nested, {'x': ['a']*1001}, {'x': 'a'*513}, {'x': 2**54}):
            with self.subTest(limit=value.keys()), self.assertRaises(ValueError):
                import_bundle(value, catalog)

    def test_secret_canaries_paths_and_claims_rejected(self):
        base, catalog = fixture()
        for key in ('token', 'password', 'body', 'resource_id', 'artifact_path', 'truths', 'predictions', 'reviewed'):
            for target in ('bundle', 'observation', 'provenance'):
                data = deepcopy(base)
                where = {'bundle': data, 'observation': data['observations'][0],
                         'provenance': data['observations'][0]['provenance']}[target]
                where[key] = 'secret-canary'
                with self.subTest(key=key, target=target), self.assertRaises(ValueError):
                    import_bundle(data, catalog)
        for value in ('../secret', '/tmp/secret', 'https://example.test', 'Bearer secret-canary'):
            data = deepcopy(base)
            data['observations'][0]['provenance']['artifact_ref'] = value
            with self.subTest(path=value), self.assertRaises(ValueError):
                import_bundle(data, catalog)


class EnvelopeTests(unittest.TestCase):
    def resign(self, data):
        data['content_digest'] = _digest({k: v for k, v in data.items() if k != 'content_digest'})
        return data

    def test_exact_bytes_roundtrip_and_schema1_compatibility(self):
        source, catalog = fixture()
        dto = import_bundle(source, catalog)
        self.assertEqual(dto['schema_version'], 2)
        self.assertEqual(validate_envelope(json.dumps(dto).encode()), dto)
        for entry in dto['artifacts']:
            raw = base64.b64decode(''.join(entry['receipt_base64_chunks']))
            self.assertEqual(raw, catalog[entry['artifact_ref']])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['artifact_hash'])
        old = import_bundle(source, catalog, output_schema_version=1)
        self.assertNotIn('receipt_encoding', old['artifacts'][0])
        with self.assertRaises(ValueError):
            validate_envelope(old)
        for obs in source['observations']:
            obs['provenance'] = None
        old = import_bundle(source, {}, output_schema_version=1)
        self.assertEqual(validate_envelope(old), old)
        for invalid in (True, 0, 3):
            with self.subTest(version=invalid), self.assertRaises(ValueError):
                import_bundle(source, {}, output_schema_version=invalid)

    def test_execution_rewrite_with_recomputed_digest_rejected(self):
        source, catalog = fixture()
        dto = import_bundle(source, catalog)
        for field, value in [('execution_id', 'execution-'+'8'*32),
                             ('signal', 'ACCESS_ALLOWED'), ('method', 'T18'),
                             ('manifest_digest', '0'*64),
                             ('manifest_version', 'sha256:'+'0'*64)]:
            changed = deepcopy(dto)
            changed['observations'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_envelope(self.resign(changed))
        changed = deepcopy(dto)
        changed['observations'][0].update(execution_status='NOT_RUN', signal='UNKNOWN')
        with self.assertRaises(ValueError):
            validate_envelope(self.resign(changed))
        # Rebuild a fully consistent new revision/cohort; old receipt still rejects.
        source['manifest'] = CaseManifest.build([case(policy_version='v2'), case('2')]).to_dict()
        revised = CaseManifest.from_dict(source['manifest'])
        for obs in source['observations']:
            c = next(c for c in revised.cases if c.actor_alias == obs['case_revision']['actor_alias'])
            obs.update(manifest_digest=revised.content_digest, manifest_version=revised.version,
                       case_revision=c.to_dict())
        changed = deepcopy(dto)
        changed.update(manifest=source['manifest'], observations=source['observations'])
        with self.assertRaises(ValueError):
            validate_envelope(self.resign(changed))

    def test_legacy_provenance_positive_and_binding(self):
        source, catalog = fixture()
        alias = 'source-'+'9'*32
        ref = 'artifact-'+'7'*32
        raw = json.dumps(dict(schema_version=1, kind='LEGACY_INVENTORY', method='ZAP',
                              source_alias=alias, linkage_status='UNLINKED')).encode()
        provenance = dict(artifact_ref=ref, artifact_hash=hashlib.sha256(raw).hexdigest(),
                          producer_kind='ZAP', producer_version='1.0', operator_alias=None)
        source['legacy'] = [dict(method='ZAP', source_alias=alias, provenance=provenance)]
        dto = import_bundle(source, catalog | {ref: raw})
        self.assertEqual(validate_envelope(dto), dto)
        self.assertEqual(dto['legacy'][0]['linkage_status'], 'UNLINKED')
        self.assertEqual(dto['legacy'][0]['conclusion'], 'UNKNOWN')
        for key, value in [('source_alias', 'source-'+'6'*32), ('method', 'T18'),
                           ('linkage_status', 'LINKED'), ('conclusion', 'ACCESS_ALLOWED')]:
            changed = deepcopy(dto)
            changed['legacy'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_envelope(self.resign(changed))

    def test_envelope_tamper_duplicate_unknown_encoding_and_limits(self):
        source, catalog = fixture()
        dto = import_bundle(source, catalog)
        mutations = [lambda d: d.update(schema_version=True),
                     lambda d: d.update(schema_version=1),
                     lambda d: d.update(attestation_status='TRUSTED'),
                     lambda d: d.update(extra='secret-canary'),
                     lambda d: d['artifacts'].append(deepcopy(d['artifacts'][0])),
                     lambda d: d['artifacts'].pop(),
                     lambda d: d['artifacts'][0].update(artifact_hash='0'*64),
                     lambda d: d['artifacts'][0].update(size_bytes=True),
                     lambda d: d['artifacts'][0].update(size_bytes=1),
                     lambda d: d['artifacts'][0].update(integrity_status='TRUSTED'),
                     lambda d: d['artifacts'][0].update(attestation_status='TRUSTED'),
                     lambda d: d['artifacts'][0].update(receipt_encoding='utf-8'),
                     lambda d: d['artifacts'][0].update(receipt_base64_chunks=['!!!!']),
                     lambda d: d['artifacts'][0].update(receipt_base64_chunks=['Zg===']),
                     lambda d: d['artifacts'][0].update(receipt_base64_chunks=['Zh==']),
                     lambda d: d['artifacts'][0].update(receipt_base64_chunks=['a']*12),
                     lambda d: d['artifacts'][0].update(receipt_base64_chunks=['a'*513]),
                     lambda d: d['artifacts'][0].update(receipt_base64_chunks=['', 'YQ==']),
                     lambda d: d['artifacts'][0].update(body='secret-canary')]
        for mutation in mutations:
            changed = deepcopy(dto)
            mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_envelope(self.resign(changed))
        changed = deepcopy(dto)
        changed['observations'][0]['execution_id'] = 'execution-'+'8'*32
        with self.assertRaises(ValueError):
            validate_envelope(changed)
        for raw in (b'{"a":1,"a":2}', b'\xff', b' '*2_000_001):
            with self.subTest(raw=raw[:10]), self.assertRaises(ValueError):
                validate_envelope(raw)
        with patch('authz_lab.evaluation.importer.MAX_ARTIFACT_BYTES', 10), self.assertRaises(ValueError):
            validate_envelope(dto)
        with patch('authz_lab.evaluation.importer.MAX_ARTIFACT_TOTAL_BYTES', 10), self.assertRaises(ValueError):
            validate_envelope(dto)

    def test_receipt_duplicate_unknown_and_invalid_utf8_with_matching_hash(self):
        source, catalog = fixture()
        ref = next(iter(catalog))
        parsed = json.loads(catalog[ref])
        for raw in (catalog[ref][:-1]+b', "schema_version":1}',
                    json.dumps(parsed | {'body': 'secret-canary'}).encode(), b'\xff',
                    json.dumps(parsed | {'execution_id': 'execution-'+'8'*32}).encode()):
            dto = import_bundle(source, catalog)
            entry = next(e for e in dto['artifacts'] if e['artifact_ref'] == ref)
            encoded = base64.b64encode(raw).decode()
            entry.update(artifact_hash=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw),
                         receipt_base64_chunks=[encoded[i:i+512] for i in range(0, len(encoded), 512)])
            next(o for o in dto['observations'] if o['provenance']['artifact_ref'] == ref)['provenance']['artifact_hash'] = entry['artifact_hash']
            with self.subTest(raw=raw[:10]), self.assertRaises(ValueError):
                validate_envelope(self.resign(dto))
