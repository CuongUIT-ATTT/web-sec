import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from authz_lab.disposable.manifest import BflaManifestError, write_manifest
from authz_lab.disposable import runner
from authz_lab.evaluation.bfla_evidence import _build_findings


class DisposableBflaRunnerTests(unittest.TestCase):
    run_id = "a1b2c3d4"

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.results_root = self.root / "results"
        self.run_dir = self.root / ".bfla-runs" / self.run_id
        self.project = f"vampi-bfla-{self.run_id}"
        write_manifest(self.run_id, self.results_root)
        self.actor = f"bfla-{self.run_id}-actor"
        self.victim = f"bfla-{self.run_id}-victim"
        self.control = f"bfla-{self.run_id}-delete-control"
        self.escalated = f"bfla-{self.run_id}-escalated"
        self.run_dir.mkdir(parents=True, mode=0o700)
        runner._write_secret(self.run_dir, {
            "run_id": self.run_id,
            "actor": {"username": self.actor, "token": "actor-token"},
            "admin": {"username": "admin", "token": "admin-token"},
        })
        for name, value in (
            ("_load_attested_preflight", ({"disposable_image_id": "image"}, {})),
            ("_assert_disposable_runtime", None),
        ):
            mock = patch.object(runner, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        block = patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden"))
        block.start()
        self.addCleanup(block.stop)
        docker = patch.object(runner.subprocess, "run", side_effect=AssertionError("Docker forbidden"))
        docker.start()
        self.addCleanup(docker.stop)

    def principal(self, username, admin=False):
        return 200, {"data": {"username": username, "admin": admin}}

    def profile(self, username):
        return 200, {"username": username, "email": username + "@example.test"}

    def execute(self, responses, extended=False):
        with patch.object(runner, "_request", side_effect=responses) as request:
            result = (runner.execute_extended.__wrapped__ if extended else runner.execute.__wrapped__)(
                self.run_id, self.project, self.run_dir, self.results_root)
        self.assertFalse(runner.artifact_has_secret_keys(result))
        self.assertNotIn("actor-token", json.dumps(result))
        return result, request

    def prefix(self):
        return [self.principal(self.actor), self.principal("admin", True)]

    def findings(self, result):
        manifest = runner.load_manifest(runner.manifest_path(self.run_id, self.results_root))
        # Exercise the persisted, sanitized producer receipt through the real consumer.
        saved = json.loads(runner.receipt_path(self.run_id, self.results_root).read_text())
        self.assertEqual(saved, result)
        return _build_findings(self.run_id, saved, manifest)

    def test_integrated_synthetic_confirmed_proof(self):
        result, request = self.execute(self.prefix() + [
            self.profile(self.victim), (204, None), (404, None)])
        proof = result["operations"]["unprivileged_delete"]["proof"]
        self.assertEqual(proof["baseline"], {"status": 200, "username": self.victim, "fresh": True})
        self.assertEqual(proof["principal"], {"status": 200, "username": self.actor, "admin": False})
        self.assertEqual(proof["postcondition"]["status"], 404)
        self.assertEqual(request.call_count, 5)
        self.assertEqual(self.findings(result)["overall_verdict"], "BFLA_CONFIRMED_DESTRUCTIVE")
        self.assertNotIn("email", json.dumps(result))

    def test_integrated_synthetic_denied_control(self):
        result, request = self.execute(self.prefix() + [
            self.profile(self.victim), (401, None), self.profile(self.victim),
            self.profile(self.control), self.principal("admin", True), (200, None), (404, None)])
        self.assertEqual(request.call_count, 9)
        self.assertEqual(self.findings(result)["overall_verdict"], "DENIED_CONTROL")
        self.assertTrue(result["operations"]["admin_delete_control"]["proof"]["principal"]["admin"])

    def test_integrated_unknown_or_survivor_is_inconclusive(self):
        for response in [(401, None), (500, None), (200, None),
                         (200, {"username": "wrong"}), self.profile(self.victim)]:
            with self.subTest(response=response):
                result, _ = self.execute(self.prefix() + [self.profile(self.victim), (200, None), response])
                self.assertEqual(self.findings(result)["overall_verdict"], "INCONCLUSIVE")
                if result["operations"]["unprivileged_delete"]["target_survived"] is None:
                    self.assertIsNone(result["operations"]["unprivileged_delete"]["proof"]["postcondition"]["status"])
                runner.receipt_path(self.run_id, self.results_root).unlink()

    def test_integrated_principal_mismatch_does_not_emit_receipt(self):
        with patch.object(runner, "_request", side_effect=[self.principal("wrong")]) as request:
            with self.assertRaises(runner.BflaExecutionError):
                runner.execute.__wrapped__(self.run_id, self.project, self.run_dir, self.results_root)
        self.assertEqual(request.call_count, 1)
        self.assertFalse(runner.receipt_path(self.run_id, self.results_root).exists())

    def test_integrated_consumer_rejects_contradictory_producer_receipt(self):
        result, _ = self.execute(self.prefix() + [self.profile(self.victim), (204, None), (404, None)])
        manifest = runner.load_manifest(runner.manifest_path(self.run_id, self.results_root))
        for field in ("summary", "principal", "baseline", "postcondition"):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(result))
                proof = changed["operations"]["unprivileged_delete"]["proof"]
                if field == "summary":
                    changed["outcome"] = "DENIED_CONTROL"
                elif field == "principal":
                    proof[field]["username"] = "wrong"
                elif field == "baseline":
                    proof[field]["fresh"] = False
                else:
                    proof[field]["status"] = None
                self.assertEqual(_build_findings(self.run_id, changed, manifest)["overall_verdict"], "INCONCLUSIVE")

    def test_rejects_out_of_scope_request(self):
        for path, method in [("/books/v1/anything", "GET"), ("/users/v1/anything", "PUT")]:
            with self.assertRaises(BflaManifestError):
                runner._assert_request_scope(path, method, None)

    def test_denied_control(self):
        result, _ = self.execute(self.prefix() + [
            self.profile(self.victim), (401, None), self.profile(self.victim),
            self.profile(self.control), self.principal("admin", True), (200, None), (404, None)])
        self.assertEqual(result["outcome"], "DENIED_CONTROL")

    def test_deletion_proof_requires_valid_baseline(self):
        result, request = self.execute(self.prefix() + [
            self.profile(self.victim), (204, None), (404, None)])
        self.assertEqual(result["outcome"], "BFLA_CONFIRMED_DESTRUCTIVE")
        self.assertEqual(request.call_count, 5)

    def test_success_status_with_surviving_victim_is_inconclusive(self):
        result, _ = self.execute(self.prefix() + [
            self.profile(self.victim), (200, None), self.profile(self.victim)])
        self.assertEqual(result["outcome"], "INCONCLUSIVE")

    def test_invalid_postconditions_never_prove_absence(self):
        for response in [(401, None), (403, None), (500, None), (200, None),
                         (200, {"username": "wrong"}), (200, [])]:
            with self.subTest(response=response):
                result, _ = self.execute(self.prefix() + [self.profile(self.victim), (200, None), response])
                self.assertEqual(result["outcome"], "INCONCLUSIVE")
                self.assertIsNone(result["operations"]["unprivileged_delete"]["target_survived"])
                runner.receipt_path(self.run_id, self.results_root).unlink()

    def test_invalid_baseline_stops_before_delete(self):
        for response in [(404, None), (500, None), (200, None), self.profile("wrong")]:
            with self.subTest(response=response), patch.object(
                runner, "_request", side_effect=self.prefix() + [response]
            ) as request:
                with self.assertRaises(runner.BflaExecutionError):
                    runner.execute.__wrapped__(self.run_id, self.project, self.run_dir, self.results_root)
                self.assertTrue(all(call.args[1] == "GET" for call in request.call_args_list))

    def test_invalid_principal_or_role_stops_before_writes(self):
        for response in [self.principal("wrong"), self.principal(self.actor, True),
                         (401, None), (200, {"data": {"username": self.actor, "admin": 0}})]:
            with self.subTest(response=response), patch.object(runner, "_request", return_value=response) as request:
                with self.assertRaises(runner.BflaExecutionError):
                    runner.execute_extended.__wrapped__(self.run_id, self.project, self.run_dir, self.results_root)
                self.assertEqual(request.call_count, 1)

    def extended_responses(self, *, victim_identity=None, email_after=None, deletion=(404, None)):
        return self.prefix() + [
            self.profile(self.victim), self.profile(self.actor),
            (204, None), email_after or self.profile(self.victim),
            (200, {"username": self.actor, "email": f"probe-{self.run_id}@example.test"}),
            self.profile(self.victim), (401, None), (204, None),
            (200, {"auth_token": "victim-token"}),
            self.principal(victim_identity or self.victim),
            (201, None), (200, {"auth_token": "escalated-token"}),
            self.principal(self.escalated, True), self.profile(self.victim),
            (200, None), deletion,
        ]

    def test_extended_positive_and_self_update(self):
        result, _ = self.execute(self.extended_responses(), extended=True)
        ops = result["operations"]
        self.assertEqual(ops["cross_user_email_update"]["verdict"], "FALSE_POSITIVE_HTTP_204_SELF_UPDATE")
        self.assertEqual(ops["cross_user_credential_update"]["verdict"], "WRITE_BOLA_CONFIRMED_ACCOUNT_TAKEOVER")
        self.assertEqual(ops["mass_assignment_registration"]["verdict"], "MASS_ASSIGNMENT_PRIVILEGE_ESCALATION_CONFIRMED")

    def test_password_principal_mismatch_is_invalid(self):
        with self.assertRaises(runner.BflaExecutionError):
            self.execute(self.extended_responses(victim_identity=self.actor), extended=True)
        self.assertFalse(runner.extended_receipt_path(self.run_id, self.results_root).exists())

    def test_extended_unknown_state_is_not_confirmed(self):
        result, _ = self.execute(self.extended_responses(email_after=(500, None), deletion=(500, None)), extended=True)
        ops = result["operations"]
        self.assertEqual(ops["cross_user_email_update"]["verdict"], "DENIED_OR_INCONCLUSIVE")
        self.assertIsNone(ops["cross_user_email_update"]["victim_email_modified"])
        self.assertEqual(ops["mass_assignment_registration"]["verdict"], "DENIED_OR_INCONCLUSIVE")
        self.assertIsNone(ops["mass_assignment_registration"]["victim_deleted_by_escalated_user"])

    def test_extended_denied_does_not_confirm(self):
        responses = self.prefix() + [
            self.profile(self.victim), self.profile(self.actor), (403, None),
            self.profile(self.victim), self.profile(self.actor),
            self.profile(self.victim), (401, None), (403, None), (401, None),
            (403, None), self.profile(self.victim),
        ]
        result, _ = self.execute(responses, extended=True)
        self.assertTrue(all(op["verdict"] == "DENIED_OR_INCONCLUSIVE"
                            for op in result["operations"].values()))

    def test_admin_control_read_error_is_unknown(self):
        result, _ = self.execute(self.prefix() + [
            self.profile(self.victim), (401, None), self.profile(self.victim),
            self.profile(self.control), self.principal("admin", True), (200, None), (500, None)])
        self.assertEqual(result["outcome"], "INCONCLUSIVE")
        self.assertIsNone(result["operations"]["admin_delete_control"]["target_absent"])

    def test_password_probe_must_be_rejected_before_write(self):
        responses = self.extended_responses()
        responses[8] = (500, None)
        with patch.object(runner, "_request", side_effect=responses) as request:
            with self.assertRaises(runner.BflaExecutionError):
                runner.execute_extended.__wrapped__(self.run_id, self.project, self.run_dir, self.results_root)
        self.assertFalse(any(call.args[0].endswith("/password") for call in request.call_args_list))

    def test_cross_user_email_change_proves_write_bola(self):
        response = (200, {"username": self.victim, "email": f"probe-{self.run_id}@example.test"})
        result, _ = self.execute(self.extended_responses(email_after=response), extended=True)
        self.assertEqual(result["operations"]["cross_user_email_update"]["verdict"], "WRITE_BOLA_CONFIRMED")


if __name__ == "__main__":
    unittest.main()

class RuntimeAttestationTests(unittest.TestCase):
    def test_exact_inspect_and_reject_mismatch_before_mutation(self):
        import copy
        import json
        from subprocess import CompletedProcess
        project = 'vampi-bfla-a1b2c3d4'
        volume = project + '_vampi_db'
        digest = 'a' * 64
        container = {'Config': {'Labels': {'com.docker.compose.project': project, 'com.docker.compose.service': 'vampi', 'project.vampi_authz_lab.workflow': 'disposable-bfla-v1', 'com.docker.compose.config-hash': digest}}, 'Image': 'image', 'State': {'Running': True}, 'HostConfig': {'PortBindings': {'5000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '5003'}]}}, 'Mounts': [{'Type': 'volume', 'Name': volume, 'Destination': '/vampi/database', 'RW': True}]}
        vol = {'Name': volume, 'Labels': {'com.docker.compose.project': project, 'com.docker.compose.volume': 'vampi_db'}}
        for kind in ['valid', 'mount', 'project', 'image', 'hash', 'unknown', 'volume']:
            with self.subTest(kind=kind):
                c, v = copy.deepcopy(container), copy.deepcopy(vol)
                if kind == 'mount': c['Mounts'][0]['Name'] = 'upstream'
                if kind == 'project': c['Config']['Labels']['com.docker.compose.project'] = 'other'
                if kind == 'image': c['Image'] = 'other'
                if kind == 'hash': c['Config']['Labels']['com.docker.compose.config-hash'] = 'b'*64
                if kind == 'unknown': del c['Mounts']
                if kind == 'volume': v['Labels']['com.docker.compose.project'] = 'other'
                commands = []
                def inspect(command, **kwargs):
                    commands.append(command)
                    if command[1] == 'inspect': output = json.dumps([c])
                    elif command[1] == 'volume': output = json.dumps([v])
                    else: output = 'vampi ' + digest
                    return CompletedProcess(command, 0, output, '')
                with patch.object(runner, '_docker_project_containers', return_value=['container']), patch.object(runner, '_docker_project_volumes', return_value=[volume]), patch.object(runner.subprocess, 'run', side_effect=inspect):
                    if kind == 'valid': runner._assert_disposable_runtime(project, 'image')
                    else:
                        with self.assertRaises(runner.BflaExecutionError): runner._assert_disposable_runtime(project, 'image')
                self.assertFalse(any('down' in command for command in commands))
