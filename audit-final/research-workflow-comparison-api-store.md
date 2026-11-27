# CMP05-B API/store implementation — PARTIAL, contract blocker

T18 OpenAPI Matrix, 2026-11-15. Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD verified `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Existing diffs preserved. Read README, comparison audit, importer handoff and independent QA, case_manifest/observations/metrics/exports contracts (metrics/exports report and contract handoff); repository file inventory contained no AGENTS.md. No runtime database/lab/network/Docker/browser/login/deployment/commit/push/reset/evidence deletion. Historical runs, including Run #2, are not joined, rewritten or read.

## Contract and blocker

Serialized importer DTO schema 1 accepted as JSON request body; canonical SHA-256 content_digest covers all output fields except content_digest, using sorted keys/compact separators/ASCII. Backend independently owns pure case/observation validation snapshots; no authz_lab imports or subprocess. These copies originate from CMP05-A case_manifest.py/observations.py and require coordinated schema evolution, not runtime CLI coupling.

Revalidates exact fields/types, schema, manifest digest/version/membership, case revisions, observation cohort binding and unique method/execution/case, explicit unique method execution selections, legacy UNLINKED/UNKNOWN, bounded catalog membership/hash/status/size and conflicting ref binding. Selections may name an empty execution per importer contract: no latest inference or execution claim. Unknown fields (including metric/truth/review claims), unsafe aliases, duplicate JSON keys, malformed JSON and limits reject with fixed errors. Limits mirror importer: 2,000,000 request/canonical bytes, 1000 items, depth 12, strings 512, integers 2**53, no floats; catalog 4096 bytes/entry and 2,000,000 total. Read inventory is paginated, maximum 100 rows.

**BLOCKER: schema-1 serialized DTO omits receipt bytes and receipt binding.** A client can change execution_id in observations, recompute content_digest, and retain the old opaque artifact_hash. The backend cannot derive a receipt preimage from SHA-256. Accepting HASH_MATCHED would not revalidate exact receipt binding. Following fail-closed assignment, every provenance-bearing DTO is rejected (422), even when its structural catalog is consistent. Only provenance-free DTOs persist; attestation remains UNVERIFIED and legacy remains UNLINKED. No eligibility/truth/metric is generated. Valid symbolic labels cannot be guaranteed secret-free: upstream sanitization remains necessary.

Full importer integration therefore remains BLOCKED, not PASS. Required upstream extension: versioned serialized envelope with bounded sanitized receipt bytes (exact encoding/hash contract), so backend can compute source hash and compare exact manifest/case/execution/status/signal receipt binding. This needs importer ownership coordination; existing importer files were not modified. Receipt integrity would still not prove source/human attestation. No claim of full CMP05 completion.

## Routes and persistence

- POST `/api/projects/{project_id}/comparisons`: admin session plus CSRF, application/json, streamed byte cap; 201 for new or identical existing content; 401/403 auth/CSRF, 404 project, 413 size, 415 media, 422 malformed/conflicting input. No lab/worker enqueue.
- GET same path: admin, project inventory with offset/limit; digest and UNVERIFIED status.
- GET `/api/projects/{project_id}/comparisons/{digest}`: admin, exact project scope, validated full DTO; 404 cross-project/missing, 409 corrupt persisted content.

Additive `comparison_bundles` table: project FK, digest, canonical JSON, created timestamp; unique(project_id,digest). No update/delete route. Duplicate insert races resolve by unique constraint and re-read; different canonical data for same digest rejects. Application API is immutable, not DB-administrator tamper-proof. Reads revalidate persisted digest/schema. Existing single-admin convention grants that admin access to all projects; project scope prevents a digest detail lookup from crossing its URL project. No invented multi-user ownership policy.

Files: new backend/app/comparison/{__init__,case_manifest,observations,validation}.py, services/comparison_evidence.py, api/comparison_routes.py, tests/test_comparison_store_api.py; minimal app/main.py router registration and persistence/models.py additive model only. Frontend/CLI/three QA status docs untouched.

## Fresh verification

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python /tmp/verify_cmp.py`: **3 tests PASS, exit 0** after final code change. Wrapper runs pytest with `-q -p no:cacheprovider --basetemp <private TemporaryDirectory>/pytest`. Tests use separate SQLite tmp_path and patch worker to no-op. In-process guards reject socket connect/connect_ex/sendto/create_connection, DNS getaddrinfo/gethostbyname/gethostbyname_ex, subprocess.Popen, os.system/posix_spawn/posix_spawnp/fork. No external calls occurred; guards are not an OS sandbox.

Checks: wrong password/anonymous/CSRF, project missing/cross-project, idempotency, reload persistence, corrupt stored DTO, limits/media errors, canonical tamper/duplicate/unknown/revision/cohort/catalog errors, secret field canary absent from errors, legacy UNLINKED, and explicit provenance-binding fail-closed. Fixtures synthetic; no claim importer full positive receipt integration, operational attestation, concurrency stress or benchmark. Existing pytest-asyncio and Starlette deprecation warnings only. Initial two-test runs passed before dedicated fail-closed test was added.

`git diff --check`: exit 0 (checked again after report). Source/test hashes before/after final test identical, listed below. Automation inspection: bot has no automations (2026-11-15T16:25:52Z).

CMP06 UI can consume inventory/detail shape for source-free snapshots but must expose UNVERIFIED and contract blocker, not claim completed integration. CMP07 real acceptance/3+ roles NOT_RUN; Browser E2E BLOCKED. Independent QA pending; overall PARTIAL.

## SHA-256 before = after

- `backend/app/comparison/__init__.py`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `backend/app/comparison/validation.py`: `eed2172643da55a4e1fafe03787d1b90054258205cbe650dd1855f2c15e40048`
- `backend/app/comparison/case_manifest.py`: `38fb21fecc9b6a40dbc558a38b0f9e99956e76dfc1701903de0d638b9d8f9fb3`
- `backend/app/comparison/observations.py`: `72cda5b6d69603672392ef913382e3920ddf7213d5fb9f9432263f17823bcf69`
- `backend/app/services/comparison_evidence.py`: `a5011c34da0ea131ee26b51d2e4cff486fae2bfc9903b2b73ec2cdbeabd1c865`
- `backend/app/api/comparison_routes.py`: `af6b26e6776c9e142b2aa33e23a7411f7c4a168d498903eecaf898e6cdfc39b4`
- `backend/app/main.py`: `eadae2f1574e35329204741f5ae04ea4c6f77b09e1c8ddc6341cebe8c8ebe9ba`
- `backend/app/persistence/models.py`: `02797f487b6983683e8f2d7a7f043552979fa634969fafdbff664b069df5919d`
- `backend/tests/test_comparison_store_api.py`: `f6b7d5200c8338ee42136f7d1a8487f951871b5ed2f0d1b92a6048f12a0d4a8a`
