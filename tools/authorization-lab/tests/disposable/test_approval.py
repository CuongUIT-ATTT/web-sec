"""Synthetic local approvals; no operational authorization or lab evidence."""
import copy
import json
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from authz_lab.disposable import approval, runner
from authz_lab.disposable.manifest import BflaManifestError, build_manifest, write_manifest
from authz_lab.evaluation.bfla_evidence import _build_findings


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.run_id = 'a1b2c3d4'
        self.run_dir = self.root / '.bfla-runs' / self.run_id
        self.run_dir.mkdir(parents=True)
        self.results = self.root / 'evidence'
        write_manifest(self.run_id, self.results)
        self.manifest = build_manifest(self.run_id)
        self.path = self.root / 'approval.json'
        self.record = {
            'schema_version': 1, 'run_id': self.run_id, 'stage': 'execute',
            'manifest_digest': approval.digest(self.manifest),
            'scope_digest': approval.digest(self.manifest['execution_scopes']['execute']),
            'issued_at': 1000, 'expires_at': 1100, 'nonce': 'a' * 32,
            'operator': 'synthetic-operator', 'provenance': 'local-operator-acknowledgement',
        }
        for target, name in [(socket.socket, 'connect'), (socket.socket, 'connect_ex'), (subprocess, 'Popen'), (subprocess, 'run')]:
            guard = patch.object(target, name, side_effect=AssertionError('external side effect blocked'))
            guard.start()
            self.addCleanup(guard.stop)

    def save(self, record=None):
        value = self.record if record is None else record
        self.path.write_text(json.dumps(value))
        return approval.digest(value)

    def call(self, **kwargs):
        return runner.execute(self.run_id, self.manifest['target']['compose_project'], self.run_dir, self.results, **kwargs)

    def test_invalid_approvals_reject_before_runtime_secret_or_http(self):
        variants = []
        for field, value in [('stage', 'execute-extended'), ('run_id', 'b1c2d3e4'), ('manifest_digest', '0'*64),
                             ('scope_digest', '0'*64), ('expires_at', 999), ('issued_at', 1051),
                             ('operator', ''), ('provenance', 'bot-message'), ('nonce', 'short')]:
            item = copy.deepcopy(self.record)
            item[field] = value
            variants.append(item)
        variants += [{}, {'schema_version': 1}]
        with patch.object(approval.time, 'time', return_value=1050), patch.object(runner, '_load_attested_preflight') as preflight, patch.object(runner, '_load_secret') as secret, patch.object(runner, '_request') as request:
            for value in variants:
                with self.subTest(record=value):
                    pin = self.save(value)
                    with self.assertRaises((BflaManifestError, ValueError)):
                        self.call(approval=self.path, approval_digest=pin)
            with self.assertRaises(BflaManifestError):
                self.call()
            pin = self.save()
            self.path.write_text(self.path.read_text().replace('synthetic-operator', 'tampered'))
            with self.assertRaises(BflaManifestError):
                self.call(approval=self.path, approval_digest=pin)
            preflight.assert_not_called()
            secret.assert_not_called()
            request.assert_not_called()
        self.assertFalse((self.run_dir / '.execute-approval-used').exists())

    def test_valid_claim_is_one_use_even_after_failure(self):
        pin = self.save()
        with patch.object(approval.time, 'time', return_value=1050), patch.object(runner, '_load_attested_preflight', side_effect=RuntimeError('synthetic failure')) as preflight:
            with self.assertRaises(RuntimeError):
                self.call(approval=self.path, approval_digest=pin)
            with self.assertRaises(FileExistsError):
                self.call(approval=self.path, approval_digest=pin)
            self.assertEqual(preflight.call_count, 1)

    def test_legacy_manifest_readable_but_execution_rejected(self):
        legacy = copy.deepcopy(self.manifest)
        legacy['schema_version'] = 1
        del legacy['execution_scopes']
        from authz_lab.disposable.manifest import validate_manifest
        validate_manifest(legacy)
        with self.assertRaises(BflaManifestError):
            approval.consume_approval(legacy, 'execute', self.run_dir, self.path, self.save(), now=1050)

    def test_caps_and_exact_stage_scope_enforced_before_transport(self):
        budget = approval.RequestBudget(self.manifest, 'execute')
        context = approval.current_budget.set(budget)
        self.addCleanup(approval.current_budget.reset, context)
        with patch.object(runner, 'urlopen') as transport:
            for path, method, payload in [('/createdb', 'GET', None), ('/users/v1/unrelated', 'DELETE', None),
                                           (f'/users/v1/bfla-{self.run_id}-victim/email', 'PUT', {'email': 'x'}),
                                           ('/users/v1/register', 'POST', {})]:
                with self.subTest(path=path), self.assertRaises(BflaManifestError):
                    runner._request(path, method, payload=payload)
            transport.assert_not_called()
            response = transport.return_value.__enter__.return_value
            response.read.return_value = b'{}'
            response.status = 200
            for _ in range(9):
                runner._request('/me', 'GET', allow_extended_scope=True)
            with self.assertRaises(BflaManifestError):
                runner._request('/me', 'GET', allow_extended_scope=True)
            self.assertEqual(transport.call_count, 9)

    def test_nonfinite_or_boolean_expiry_rejected(self):
        for value in (float("nan"), float("inf"), -1, True):
            record = copy.deepcopy(self.record)
            record["expires_at"] = value
            self.path.write_text(json.dumps(record))
            with self.subTest(value=value), self.assertRaises(ValueError):
                approval.consume_approval(self.manifest, 'execute', self.run_dir, self.path, 'a' * 64, now=1050)

    def test_redirect_cannot_bypass_request_budget(self):
        with self.assertRaises(BflaManifestError):
            runner._RejectRedirects().redirect_request(None, None, 302, 'redirect', {}, 'http://127.0.0.1:5000')

    def test_extended_payload_and_principal_binding(self):
        budget = approval.RequestBudget(self.manifest, 'execute-extended')
        for payload in [{'username': 'admin', 'password': 'synthetic'}, {'username': f'bfla-{self.run_id}-victim', 'password': 'x', 'extra': True}]:
            with self.assertRaises(BflaManifestError):
                budget.consume('/users/v1/login', 'POST', payload)
        budget.consume('/users/v1/login', 'POST', {'username': f'bfla-{self.run_id}-victim', 'password': 'synthetic'})
        with self.assertRaises(BflaManifestError):
            budget.consume('/users/v1/register', 'POST', {'username': f'bfla-{self.run_id}-victim', 'password': 'x', 'email': 'x', 'admin': True})

    def test_approved_producer_to_real_consumer(self):
        pin = self.save()
        actor = f'bfla-{self.run_id}-actor'
        victim = f'bfla-{self.run_id}-victim'
        responses = [(200, {'data': {'username': actor, 'admin': False}}),
                     (200, {'data': {'username': 'admin', 'admin': True}}),
                     (200, {'username': victim}), (204, None), (404, None)]
        with patch.object(approval.time, 'time', return_value=1050), patch.object(runner, '_load_attested_preflight', return_value=({'disposable_image_id': 'synthetic'}, {})), patch.object(runner, '_assert_disposable_runtime'), patch.object(runner, '_load_secret', return_value={'run_id': self.run_id, 'actor': {'username': actor, 'token': 'synthetic-actor'}, 'admin': {'username': 'admin', 'token': 'synthetic-admin'}}), patch.object(runner, '_request', side_effect=responses):
            result = self.call(approval=self.path, approval_digest=pin)
        self.assertEqual(_build_findings(self.run_id, result, self.manifest)['overall_verdict'], 'BFLA_CONFIRMED_DESTRUCTIVE')
        self.assertIsNone(approval.current_budget.get())
