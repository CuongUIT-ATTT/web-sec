"""Synthetic contract fixtures only; no lab execution or reviewed ground truth."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import tempfile
import unittest

from authz_lab.evaluation.case_manifest import CaseDefinition, CaseManifest


def sample(**changes):
    values = dict(method='GET', operation_template='/users/v1/{username}',
                  actor_alias='actor-' + 'a' * 32, actor_role='userA',
                  owner_alias='owner-' + 'b' * 32, owner_category='OTHER',
                  fixture_version='v1', fixture_hash='c' * 64,
                  policy_id='cross_user', policy_version='v1', expected_decision='DENY')
    return CaseDefinition(**(values | changes))


class CaseManifestTests(unittest.TestCase):
    def test_stable_order_independent_serialization_and_json_roundtrip(self):
        first, second = sample(), sample(actor_alias='actor-' + 'd' * 32)
        a, b = CaseManifest.build([first, second]), CaseManifest.build([second, first])
        self.assertEqual(a.to_dict(), b.to_dict())
        with tempfile.TemporaryDirectory(prefix='cmp02-') as tmp:
            path = Path(tmp) / 'synthetic.json'
            path.write_text(json.dumps(a.to_dict()), encoding='utf-8')
            self.assertEqual(CaseManifest.from_dict(json.loads(path.read_text())), a)
        self.assertEqual(a.require_case(first.case_id), first)
        self.assertEqual(len(first.case_id), 69)
        self.assertNotIn(first.actor_role, first.case_id)

    def test_every_semantic_change_changes_case_and_cohort_version(self):
        original = sample()
        baseline = CaseManifest.build([original])
        alternatives = dict(method='HEAD', operation_template='/books/v1/{title}',
                            actor_alias='actor-' + 'e' * 32, actor_role='admin',
                            owner_alias='owner-' + 'e' * 32, owner_category='SELF',
                            fixture_version='v2', fixture_hash='d' * 64,
                            policy_id='other_policy', policy_version='v2', expected_decision='ALLOW')
        for name, value in alternatives.items():
            with self.subTest(field=name):
                updated = replace(original, **{name: value})
                self.assertNotEqual(original.case_id, updated.case_id)
                self.assertNotEqual(baseline.version, CaseManifest.build([updated]).version)

    def test_duplicates_conflicting_scenarios_and_unknown_case_rejected(self):
        for cases in ([], [sample(), sample()], [sample(), sample(expected_decision='ALLOW')]):
            with self.subTest(cases=len(cases)), self.assertRaises(ValueError):
                CaseManifest.build(cases)
        with self.assertRaises(ValueError):
            CaseManifest.build([sample()]).require_case('legacy-M-01')

    def test_missing_unknown_fields_and_tampering_fail_closed(self):
        for name in sample().to_dict():
            data = sample().to_dict()
            del data[name]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                CaseDefinition.from_dict(data)
        data = sample().to_dict() | {'token': 'redaction-canary'}
        with self.assertRaises(ValueError):
            CaseDefinition.from_dict(data)
        for key, value in [('version', 'v2'), ('content_digest', '0' * 64), ('schema_version', True), ('schema_version', 2), ('cases', []), ('run_id', 2)]:
            data = CaseManifest.build([sample()]).to_dict() | {key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                CaseManifest.from_dict(data)
        data = sample().to_dict() | {'actor_role': 'admin'}
        with self.assertRaises(ValueError):
            CaseDefinition.from_dict(data)
        for payload in (None, [], {}, 'invalid'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                CaseManifest.from_dict(payload)

    def test_invalid_values_and_rendered_paths_rejected(self):
        invalid = dict(method=['get', 'TRACE', None, True, []],
                       operation_template=['https://example.com/users', '/users/123', '/users?token=x', '/users/../me', '/users/%61', '/users//me', '/users/#x', None, ''],
                       actor_alias=['alice', 'actor-alice', 'owner-' + 'a' * 32, None],
                       owner_alias=['bob', 'actor-' + 'a' * 32, None],
                       actor_role=['', 'Bearer secret', None],
                       owner_category=['UNKNOWN', None, []],
                       fixture_hash=['F' * 64, '0' * 63, None],
                       fixture_version=['', None], policy_id=['', None], policy_version=['', None],
                       expected_decision=['UNKNOWN', 'allow', None, []])
        for key, values in invalid.items():
            for value in values:
                with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                    sample(**{key: value})

    def test_immutability_and_detached_serialization(self):
        case = sample()
        manifest = CaseManifest.build([case])
        with self.assertRaises(FrozenInstanceError):
            case.actor_role = 'admin'
        with self.assertRaises(FrozenInstanceError):
            manifest.cases = ()
        with self.assertRaises(ValueError):
            CaseManifest([case])
        exported = manifest.to_dict()
        exported['cases'][0]['actor_role'] = 'admin'
        self.assertEqual(manifest.cases[0].actor_role, 'userA')

    def test_public_and_unowned_categories_require_null_owner(self):
        for category in ('PUBLIC', 'NONE'):
            with self.subTest(category=category):
                self.assertIsNone(sample(owner_category=category, owner_alias=None).owner_alias)
                with self.assertRaises(ValueError):
                    sample(owner_category=category)

    def test_methods_share_contract_without_execution_authorization(self):
        for method in ('GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE'):
            with self.subTest(method=method):
                self.assertEqual(sample(method=method).method, method)

    def test_v1_digest_golden_vector(self):
        self.assertEqual(sample().case_id, 'case-f3ae6e5194bba9d3fdb7387dbbfbb99d439a74dc114dc29b5b51add05d9ca087')
        self.assertEqual(CaseManifest.build([sample()]).content_digest, '30a380c315f849770ce0a5bb14e9d71db0056bca188fe1ec71fe87df1fd942aa')

    def test_numeric_and_semver_versions(self):
        for version in ('1', 'v2', '1.2.3', 'release-2'):
            with self.subTest(version=version):
                self.assertEqual(sample(fixture_version=version, policy_version=version).policy_version, version)
