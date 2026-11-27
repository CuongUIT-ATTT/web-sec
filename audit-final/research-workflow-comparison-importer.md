# CMP05-A — pure comparison importer

T18 ZAP Comparison, 2026-11-15. Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD verified `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Read root/lab README, comparison audit, case-manifest/observations/metrics/exports contracts and source/tests. No AGENTS.md found in repository or checked ancestor directories. Preserved existing diff. Only created `evaluation/importer.py`, `tests/evaluation/test_importer.py` and this report under assigned paths.

**PASS implementation regression; overall PARTIAL. Experiments NOT_RUN.** No real reviewed ground truth, human attestation or source authentication established. No orchestration/API/UI or historical import performed. No runtime, Run #2, lab, ZAP, DB, Docker, deployment, commit/push/reset or evidence deletion.

## API handoff contract

`authz_lab.evaluation.importer.import_bundle(bundle, artifact_bytes) -> dict` is pure; no filesystem/network/process calls. `bundle` is explicit UTF-8 JSON bytes or JSON-compatible mapping. `artifact_bytes` is caller-owned mapping from opaque `artifact-<32 lowercase hex>` references to exact bytes. It is not a path resolver. The future backend must consume serialized JSON DTO through its own schema/store; web must never import/call this CLI package.

Input schema 1 has exact fields `schema_version`, `manifest`, `observations`, `selections`, `legacy`:

- Manifest is the exact existing CaseManifest dictionary, including schema/version/digest and full case definitions. Existing contract revalidates SHA-256, membership and all revisions. It retains reviewed operation templates/opaque aliases, never rendered resource identifiers.
- Observations use exact CMP03 payload fields and producer/method rules. Duplicate method/execution/case triples reject. Multiple executions may remain inventory. Selection is an explicit nonempty list of `{method, execution_id}`, one execution per method, never latest/history inference. A selected execution without observations remains valid so downstream can report NOT_RUN/EXECUTION_MISMATCH; it does not assert execution occurred.
- Legacy exact input `{method, source_alias, provenance}` uses existing Provenance structure or null. Duplicate method/source rejects. Output always has `linkage_status=UNLINKED`, `conclusion=UNKNOWN`, no cohort/case mapping. Historical raw reports are deliberately unsupported: an upstream reviewed redaction/mapping adapter is still needed.
- Each non-null observation provenance references a schema-1 JSON receipt with EXACT fields `{schema_version, kind: OBSERVATION, manifest_digest, manifest_version, case_id, method, execution_id, execution_status, signal}`. Each non-null legacy provenance references EXACT `{schema_version, kind: LEGACY_INVENTORY, method, source_alias, linkage_status: UNLINKED}`. These are metadata receipts, not raw reports or proof of the stated execution. Caller constructs them from reviewed sanitized inputs; importer never generates operational approval or attestation.
- Catalog membership must equal referenced artifact set. Actual SHA-256 covers supplied bytes, including whitespace; mismatch rejects. Parsed receipt must exactly equal its expected binding. Unknown fields, duplicate JSON keys, missing artifacts, unused artifacts, conflicting ref/hash/binding, malformed types, unsupported versions and case/execution tamper reject. Same reference cannot silently represent multiple cases/executions.

Limits: 2,000,000 bytes bundle (both raw and canonical serialized size); 4096 bytes per artifact (raw and canonical); 2,000,000 bytes total artifacts; 1000 entries per object/array/catalog; 512 characters per string; nesting depth 12; integers bounded to 2**53; no floats/NaN/custom JSON values. Only exact bytes accepted for artifact content. Errors contain fixed reasons, never rejected input content.

Output detached pure JSON schema 1: canonical sorted `manifest`, `observations`, `selections`, `legacy`, `artifacts`, global `attestation_status=UNVERIFIED`, and SHA-256 `content_digest` over all preceding output fields using existing canonical encoder. Catalog entries contain only ref/hash/byte length, `integrity_status=HASH_MATCHED` and `attestation_status=UNVERIFIED`; artifact bytes are not exported. Ordering is stable regardless of caller order; per-source hash intentionally changes if source bytes change.

Import does NOT accept truths/predictions/review claims or set metrics eligibility booleans. Existing evaluate still requires separate ReviewedTruth and ValidatedPrediction with baseline/protected-field/policy/source validation. Hash integrity and human metadata are not source authentication, human benchmark or ground-truth review. Structural allowlists reject secret/body/resource-ID/path fields and canaries but cannot identify secrets disguised as syntactically valid symbolic labels/templates; caller must review/redact those first. No timing values fabricated.

Future API must separately enforce project/user authorization, reviewed mapping, trust/reviewer provenance, persistence, DTO schema validation and read-only comparison routes. These concerns cannot be inferred from bytes or hashes. CMP05 API/store, CMP06 UI and CMP07 real acceptance remain dependencies; no claim of integration or link to Run #2.

## Fresh verification

Used `.venv/bin/python` with `PYTHONPATH=tools/authorization-lab/src`. Guarded `socket.socket.connect`, `connect_ex`, `socket.create_connection`, `socket.getaddrinfo`, `subprocess.Popen`, `os.system` via mocks raising AssertionError. This is a test guard, not an OS sandbox. Importer requires no temp files; existing suite uses its synthetic temp fixtures. No real HTTP/DNS/process invocation.

1. Fresh importer-only pytest: `tests/evaluation/test_importer.py -q --tb=short -p no:cacheprovider`: **8 tests + 67 subtests PASS, exit 0**.
2. Fresh combined regression: `test_case_manifest.py test_observations.py test_metrics.py test_exports.py test_importer.py` under the same evaluation directory/options/guards: **39 tests + 326 subtests PASS, fresh pytest exit 0**. SHA-256 of all ten source/test files captured before and after pytest; equality asserted, **10/10 matched**, command exit 0. No skip/xfail/failing test attempts. Existing pytest-asyncio scope deprecation warning only. Unit-test elapsed time is not method benchmark timing.
3. `git diff --check`: exit 0. New owned files additionally checked for trailing whitespace and final newline since untracked files are not covered by git diff.
4. Automation inspection: no automations for this bot.

Tests cover deterministic bytes/mapping import and detached output, existing contract interoperability, metric exclusion without separate review, empty selected execution/unverified source, legacy UNLINKED, duplicates/unknown/missing fields, revised cohort/case and execution mismatch, hash tamper even with valid JSON, schema/body tamper with recomputed hashes, missing/unused catalog, malformed UTF-8/JSON and duplicate keys, byte/total/count/depth/string/integer limits, unsafe refs and secret/body/resource-ID/review-claim canaries. Fixtures entirely synthetic; regression does not attest artifact provenance or real lab execution. Independent QA pending.

## Source/test hashes

- `tools/authorization-lab/src/authz_lab/evaluation/case_manifest.py`: `38fb21fecc9b6a40dbc558a38b0f9e99956e76dfc1701903de0d638b9d8f9fb3`

- `tools/authorization-lab/src/authz_lab/evaluation/observations.py`: `72cda5b6d69603672392ef913382e3920ddf7213d5fb9f9432263f17823bcf69`

- `tools/authorization-lab/src/authz_lab/evaluation/metrics.py`: `8993b5d23ed004f60ceea8807d744adb6cf32cc273a4cc31af785d7f5b687642`

- `tools/authorization-lab/src/authz_lab/evaluation/exports.py`: `ec4b03631399a6db3810e0261eb0c51a806cbaf5e04c0480ea313f1cf9145b1b`

- `tools/authorization-lab/src/authz_lab/evaluation/importer.py`: `e3a3b34aaf6c4dce468d43a699b4a8ca3614fc735125cc2efa9c26e89a34eb97`

- `tools/authorization-lab/tests/evaluation/test_case_manifest.py`: `be03ad6c3a672c1c606067c67d6a0942870598b39f77db54854116c14368c5ea`

- `tools/authorization-lab/tests/evaluation/test_observations.py`: `1228e6dbebeb01d13a39a910d954aefe464a9744f4d9fe82ce5ba237671158ee`

- `tools/authorization-lab/tests/evaluation/test_metrics.py`: `4b4a7d4c1cb56eb374c35be5ef1ccd53ee99d9a7bac8121740f1976c1e12b58b`

- `tools/authorization-lab/tests/evaluation/test_exports.py`: `1d09b1710d8d9007bdbc1b5a6f58382b041d6931a615d06eef38f6e66a0cc795`

- `tools/authorization-lab/tests/evaluation/test_importer.py`: `49d5a4c8fc1f47ed48c7edc8949dcd05dfd177809d53285cfa87945a0720f3d4`
