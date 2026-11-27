"""Synthetic contract tests; never proof of lab execution or reviewed truth."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import tempfile
import unittest

from authz_lab.evaluation.case_manifest import CaseDefinition, CaseManifest
from authz_lab.evaluation.observations import (
    adapt_manual, adapt_t18, adapt_zap, ObservationSet, LegacyUnlinked, Provenance,
)


def case(actor='a', **changes):
    return CaseDefinition(**(dict(method='GET', operation_template='/users/{username}',
        actor_alias='actor-' + actor * 32, actor_role='userA',
        owner_alias='owner-' + 'b' * 32, owner_category='OTHER',
        fixture_version='v1', fixture_hash='c' * 64,
        policy_id='cross_user', policy_version='v1', expected_decision='DENY') | changes))


def payload(manifest, selected=None, method='MANUAL'):
    selected = selected or manifest.cases[0]
    return dict(method=method, manifest_digest=manifest.content_digest,
        manifest_version=manifest.version, case_revision=selected.to_dict(),
        execution_id='execution-' + 'd' * 32, execution_status='COMPLETED',
        signal='ACCESS_DENIED', provenance=dict(artifact_ref='artifact-' + 'e' * 32,
            artifact_hash='f' * 64, producer_kind={'MANUAL': 'HUMAN',
            'T18': 'AUTOMATED_VERIFIER', 'ZAP': 'ZAP'}[method],
            producer_version='1.0', operator_alias='operator-' + '1' * 32 if method == 'MANUAL' else None))


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = CaseManifest.build([case(), case('2')])

    def test_all_adapters_roundtrip_and_stable_digest(self):
        for method, adapter in [('MANUAL', adapt_manual), ('T18', adapt_t18), ('ZAP', adapt_zap)]:
            with self.subTest(method=method):
                data = payload(self.manifest, method=method)
                observation = adapter(self.manifest, data)
                with tempfile.TemporaryDirectory(prefix='cmp03-') as tmp:
                    path = Path(tmp) / 'synthetic.json'
                    path.write_text(json.dumps(observation.to_dict()), encoding='utf-8')
                    restored = adapter(self.manifest, json.loads(path.read_text()))
                self.assertEqual(restored, observation)
                self.assertEqual(restored.content_digest, observation.content_digest)
                self.assertEqual(observation.conclusion, 'ACCESS_DENIED')
                self.assertEqual(observation.provenance_status, 'SOURCE_RECORDED')
                self.assertEqual(observation.human_observation_verified, method == 'MANUAL')

    def test_same_path_different_actor_never_collapses(self):
        observations = [adapt_manual(self.manifest, payload(self.manifest, c)) for c in self.manifest.cases]
        first = ObservationSet.build(self.manifest, observations)
        self.assertEqual(len(first.observations), 2)
        self.assertEqual(first, ObservationSet.build(self.manifest, reversed(observations)))
        self.assertNotEqual(observations[0].case_id, observations[1].case_id)
        with self.assertRaises(ValueError):
            ObservationSet.build(self.manifest, observations + observations[:1])

    def test_method_and_execution_identity_separate(self):
        manual = adapt_manual(self.manifest, payload(self.manifest))
        script = adapt_t18(self.manifest, payload(self.manifest, method='T18'))
        repeat = payload(self.manifest) | {'execution_id': 'execution-' + '9' * 32}
        self.assertEqual(len(ObservationSet.build(self.manifest,
            [manual, script, adapt_manual(self.manifest, repeat)]).observations), 3)

    def test_missing_source_and_automated_verifier_not_human(self):
        data = payload(self.manifest)
        unverified = adapt_manual(self.manifest, data | {'provenance': None})
        self.assertFalse(unverified.human_observation_verified)
        self.assertEqual(unverified.provenance_status, 'UNVERIFIED')
        self.assertEqual(unverified.conclusion, 'UNKNOWN')
        data['provenance']['producer_kind'] = 'AUTOMATED_VERIFIER'
        self.assertFalse(adapt_manual(self.manifest, data).human_observation_verified)

    def test_zap_access_rule_never_confirms_bola(self):
        for signal in ('ILLEGAL', 'LEGAL', 'UNKNOWN'):
            with self.subTest(signal=signal):
                observation = adapt_zap(self.manifest, payload(self.manifest, method='ZAP') | {'signal': signal})
                self.assertEqual(observation.conclusion, 'UNKNOWN')
        for signal in ('BOLA_CONFIRMED', 'TN', 'FN', 'NO_BOLA'):
            with self.subTest(signal=signal), self.assertRaises(ValueError):
                adapt_zap(self.manifest, payload(self.manifest, method='ZAP') | {'signal': signal})

    def test_noncompleted_unknown_not_negative(self):
        for status in ('NOT_RUN', 'INVALID', 'UNKNOWN', 'BLOCKED'):
            for method, adapter in [('MANUAL', adapt_manual), ('T18', adapt_t18), ('ZAP', adapt_zap)]:
                data = payload(self.manifest, method=method) | {'execution_status': status, 'signal': 'UNKNOWN'}
                with self.subTest(status=status, method=method):
                    obs = adapter(self.manifest, data)
                    self.assertEqual(obs.conclusion, 'UNKNOWN')
                    self.assertFalse(obs.human_observation_verified)
                    with self.assertRaises(ValueError):
                        adapter(self.manifest, data | {'signal': 'ACCESS_DENIED'})

    def test_mismatched_cohort_and_every_revision_rejected(self):
        data = payload(self.manifest)
        for key, value in [('manifest_digest', '0' * 64), ('manifest_version', 'sha256:' + '0' * 64)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                adapt_manual(self.manifest, data | {key: value})
        for field, value in [('actor_role', 'admin'), ('actor_alias', 'actor-' + '3' * 32),
                             ('owner_alias', 'owner-' + '4' * 32), ('policy_version', 'v2'),
                             ('policy_id', 'another'), ('fixture_version', 'v2'),
                             ('fixture_hash', '5' * 64), ('expected_decision', 'ALLOW')]:
            revised = CaseDefinition.from_dict(data['case_revision'])
            from dataclasses import replace
            changed = replace(revised, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                adapt_manual(self.manifest, data | {'case_revision': changed.to_dict()})
        other = CaseManifest.build([case('7')])
        with self.assertRaises(ValueError):
            ObservationSet.build(other, [adapt_manual(self.manifest, data)])

    def test_missing_unknown_and_malformed_fields(self):
        original = payload(self.manifest)
        for key in original:
            data = deepcopy(original)
            del data[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                adapt_manual(self.manifest, data)
        for key, values in dict(method=['T18', None, []], execution_id=['run-2', '/tmp/result', None],
                execution_status=['completed', None, [], True], signal=['BOLA_CONFIRMED', None, [], False],
                provenance=[{}, [], 'x'], case_revision=[{}, None, []]).items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    adapt_manual(self.manifest, original | {key: value})
        for key in ('body', 'token', 'resource_id', 'artifact_path', 'source_run_id'):
            with self.subTest(extra=key), self.assertRaises(ValueError):
                adapt_manual(self.manifest, original | {key: 'canary'})

    def test_provenance_exact_and_private_path_rejection(self):
        original = payload(self.manifest)
        for key in original['provenance']:
            data = deepcopy(original)
            del data['provenance'][key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                adapt_manual(self.manifest, data)
        invalid = {'artifact_ref': ['/tmp/a', '../a', 'https://a', 'artifact-secret', None],
                   'artifact_hash': ['x', 'F' * 64, None],
                   'producer_kind': ['ZAP', None, []],
                   'producer_version': ['Bearer secret', '', None],
                   'operator_alias': [None, 'alice', '/tmp/a']}
        for key, values in invalid.items():
            for value in values:
                data = deepcopy(original)
                data['provenance'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    adapt_manual(self.manifest, data)
        data = deepcopy(original)
        data['provenance']['raw_body'] = 'canary'
        with self.assertRaises(ValueError):
            adapt_manual(self.manifest, data)

    def test_immutable_detached_and_source_digest_changes(self):
        original = payload(self.manifest)
        obs = adapt_manual(self.manifest, original)
        with self.assertRaises(FrozenInstanceError):
            obs.signal = 'UNKNOWN'
        with self.assertRaises(FrozenInstanceError):
            obs.provenance.artifact_hash = '0' * 64
        exported = obs.to_dict()
        exported['provenance']['artifact_hash'] = '0' * 64
        self.assertNotEqual(obs.content_digest, adapt_manual(self.manifest, exported).content_digest)
        self.assertEqual(obs.provenance.artifact_hash, 'f' * 64)
        with self.assertRaises(ValueError):
            ObservationSet(self.manifest, [obs])

    def test_legacy_inventory_explicitly_unlinked(self):
        entry = LegacyUnlinked('ZAP', 'source-' + '1' * 32, None)
        self.assertEqual(entry.linkage_status, 'UNLINKED')
        self.assertEqual(entry.conclusion, 'UNKNOWN')
        self.assertFalse(hasattr(entry, 'case_id'))
        with self.assertRaises(ValueError):
            ObservationSet.build(self.manifest, [entry])
        with self.assertRaises(ValueError):
            LegacyUnlinked('ZAP', '/results/run2.json', None)
