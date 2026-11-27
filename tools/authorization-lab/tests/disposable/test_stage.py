"""Synthetic lifecycle/crash controls, never operational approvals."""
import json
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import BaseHandler, build_opener
from urllib.response import addinfourl
from email.message import Message
from io import BytesIO

from authz_lab.disposable import runner, stage, approval
from authz_lab.disposable.manifest import write_manifest, build_manifest, BflaManifestError


class StageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run = 'a1b2c3d4'
        self.project = 'vampi-bfla-' + self.run
        self.results = self.root / 'results'
        write_manifest(self.run, self.results)
        self.directory = self.results / self.run
        self.private = self.root / '.bfla-runs' / self.run
        for target, name in [(socket.socket, 'connect'), (socket.socket, 'connect_ex'),
                             (socket, 'getaddrinfo'), (subprocess, 'Popen'), (subprocess, 'run')]:
            guard = patch.object(target, name, side_effect=AssertionError('external blocked'))
            guard.start()
            self.addCleanup(guard.stop)

    def call(self, function):
        return function(self.run, self.project, self.private, self.results)

    def test_interrupted_prepare_never_resets_again(self):
        with patch.object(runner, '_load_attested_preflight', return_value=({'disposable_image_id': 'image'}, {})), patch.object(runner, '_assert_disposable_runtime'), patch.object(runner, '_request', side_effect=KeyboardInterrupt) as request:
            with self.assertRaises(KeyboardInterrupt):
                self.call(runner.prepare)
            self.assertTrue((self.directory / '.lifecycle-active').exists())
            with self.assertRaises(BflaManifestError):
                self.call(runner.prepare)
            self.assertEqual(request.call_count, 1)

    def test_failure_is_sanitized_and_claim_is_retained(self):
        @stage.lifecycle('prepare')
        def fail(*args):
            raise RuntimeError('password=DO-NOT-EXPORT response body')
        with self.assertRaises(RuntimeError):
            self.call(fail)
        text = (self.directory / 'prepare-stage.json').read_text()
        self.assertNotIn('DO-NOT-EXPORT', text)
        self.assertEqual(json.loads(text)['reason'], 'STAGE_FAILED')
        with self.assertRaises(BflaManifestError):
            self.call(fail)

    def test_execute_extended_race_excluded(self):
        @stage.lifecycle('execute-extended')
        def extended(*args):
            self.fail('racing stage must not run')
        @stage.lifecycle('execute')
        def execute(*args):
            with self.assertRaises(BflaManifestError):
                self.call(extended)
        self.call(execute)
        self.assertFalse((self.directory / '.execute-extended-claimed').exists())

    def test_extended_replay_rejected(self):
        calls = []
        @stage.lifecycle('execute-extended')
        def extended(*args):
            calls.append(1)
        self.call(extended)
        with self.assertRaises(BflaManifestError):
            self.call(extended)
        self.assertEqual(calls, [1])

    def test_existing_receipt_rejects_public_runner_before_approval_or_network(self):
        for name, function in [('execution-receipt.json', runner.execute), ('extended-state-receipt.json', runner.execute_extended)]:
            with self.subTest(name=name):
                path = self.directory / name
                path.write_text('historical evidence')
                with patch.object(runner, 'urlopen') as transport, patch.object(runner, 'approval_gate') as gate:
                    with self.assertRaises(BflaManifestError):
                        self.call(function)
                    transport.assert_not_called()
                    gate.assert_not_called()
                self.assertEqual(path.read_text(), 'historical evidence')

    def test_atomic_publication_never_overwrites(self):
        path = self.directory / 'receipt.json'
        stage.durable_json(path, {'status': 'old'})
        with self.assertRaises(FileExistsError):
            stage.durable_json(path, {'status': 'new'})
        self.assertEqual(json.loads(path.read_text()), {'status': 'old'})

    def test_redirect_statuses_and_transport_failure_never_retry(self):
        for code in [301, 302, 303, 307, 308]:
            with self.subTest(code=code), patch.object(runner, 'urlopen') as transport:
                response = transport.return_value.__enter__.return_value
                response.status, response.read.return_value = code, b''
                with self.assertRaises(BflaManifestError):
                    runner._request('/me', 'GET', allow_extended_scope=True)
                self.assertEqual(transport.call_count, 1)
        with patch.object(runner, 'urlopen', side_effect=OSError('failure')) as transport:
            with self.assertRaises(OSError):
                runner._request('/me', 'GET', allow_extended_scope=True)
            self.assertEqual(transport.call_count, 1)

    def test_extended_budget_exact_22_then_stop_before_transport(self):
        budget = approval.RequestBudget(build_manifest(self.run), 'execute-extended')
        context = approval.current_budget.set(budget)
        self.addCleanup(approval.current_budget.reset, context)
        with patch.object(runner, 'urlopen') as transport:
            response = transport.return_value.__enter__.return_value
            response.status, response.read.return_value = 200, b'{}'
            for _ in range(22):
                runner._request('/me', 'GET', allow_extended_scope=True)
            with self.assertRaises(BflaManifestError):
                runner._request('/me', 'GET', allow_extended_scope=True)
            self.assertEqual(transport.call_count, 22)

    def test_real_opener_rejects_redirect_without_second_transport(self):
        for code in [301, 302, 303, 307, 308]:
            calls = []
            class SyntheticTransport(BaseHandler):
                handler_order = 100
                def http_open(self, request):
                    calls.append(request.full_url)
                    headers = Message()
                    headers['Location'] = 'http://127.0.0.1:5000/createdb'
                    response = addinfourl(BytesIO(b''), headers, request.full_url, code)
                    response.msg = 'redirect'
                    return response
            opener = build_opener(SyntheticTransport(), runner._RejectRedirects())
            with self.subTest(code=code), patch.object(runner, 'urlopen', opener.open):
                with self.assertRaises(BflaManifestError):
                    runner._request('/me', 'GET', allow_extended_scope=True)
                self.assertEqual(calls, ['http://127.0.0.1:5003/me'])

    def test_http_error_redirect_does_not_retry(self):
        with patch.object(runner, 'urlopen', side_effect=HTTPError('synthetic', 302, 'redirect', {}, BytesIO(b''))) as transport:
            with self.assertRaises(BflaManifestError):
                runner._request('/me', 'GET', allow_extended_scope=True)
            self.assertEqual(transport.call_count, 1)

    def test_concurrent_execute_extended_has_one_winner(self):
        from threading import Event, Thread
        entered, release = Event(), Event()
        failures = []
        @stage.lifecycle('execute')
        def execute(*args):
            entered.set()
            if not release.wait(2):
                raise AssertionError('test coordination timeout')
        @stage.lifecycle('execute-extended')
        def extended(*args):
            self.fail('concurrent stage reached mutation')
        def worker():
            try:
                self.call(execute)
            except BaseException as error:
                failures.append(error)
        thread = Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(BflaManifestError):
                self.call(extended)
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])

    def test_public_extended_failure_then_replay_before_runtime(self):
        self.private.mkdir(parents=True)
        manifest = build_manifest(self.run)
        record = {
            'schema_version': 1, 'run_id': self.run, 'stage': 'execute-extended',
            'manifest_digest': approval.digest(manifest),
            'scope_digest': approval.digest(manifest['execution_scopes']['execute-extended']),
            'issued_at': 1000, 'expires_at': 1100, 'nonce': 'a' * 32,
            'operator': 'synthetic', 'provenance': 'local-operator-acknowledgement',
        }
        source = self.root / 'synthetic-approval.json'
        source.write_text(json.dumps(record))
        with patch.object(approval.time, 'time', return_value=1050), patch.object(runner, '_load_attested_preflight', side_effect=RuntimeError('synthetic failure')) as runtime, patch.object(runner, 'urlopen') as transport:
            for expected in [RuntimeError, BflaManifestError]:
                with self.assertRaises(expected):
                    runner.execute_extended(self.run, self.project, self.private, self.results,
                                            approval=source, approval_digest=approval.digest(record))
            self.assertEqual(runtime.call_count, 1)
            transport.assert_not_called()
        self.assertIsNone(approval.current_budget.get())
        self.assertTrue((self.private / '.execute-extended-approval-used').exists())
