# RESOURCE-ID-01 — 2026-11-25

Implementation and focused verification complete; independent QA pending. Overall T18 remains PARTIAL.

## Change

Resources retain internal aliases (`resource-N`). Each row now shows owner/name/role, resource type and path parameter, with an explicit **Xem ID đã lưu / Ẩn ID** action. The action reads persisted `external_id` via POST `/api/projects/{project_id}/resources/{resource_id}/inspect`, guarded by the existing admin session and CSRF checks. Responses set `Cache-Control: no-store` and `Pragma: no-cache`. List/create/update DTOs, matrix, runs and exports retain existing redaction. No credentials, response bodies or protected field values are returned by the inspection DTO.

Request previews show selected GET templates whose placeholder set matches this resource's path parameter, using the same `_concrete_path` helper as the execution worker (including percent encoding). These are path previews, not approval/scope checks or evidence that a lab request ran. No network call or run is triggered. Reveal state is cleared on hide, document becoming hidden, component unmount/project switch, or configuration refresh after save; nothing is written to browser storage.

## Validation

- `.venv/bin/python -m pytest backend/tests/test_resource_inspection.py backend/tests/test_research_matrix_contract.py backend/tests/test_demo_seed.py -q`: **17 passed**, exit 0. Includes 401/403/405, project scope 404, no-store, all four fixture owners, persisted replacement ID across requests, percent encoding, unselected operation exclusion and unchanged redacted list/edit contracts. One Starlette deprecation warning; pytest-asyncio also warns about its default fixture scope.
- `cd frontend && npm run test -- --reporter=dot`: **68 passed / 8 files**, exit 0. New component cases cover explicit reveal/hide, remount, hidden-document stale response, sanitized failure and retry.
- `npm run lint`, `npm run build`, `git diff --check`: exit 0. Final CSS adjustment was rebuilt and visually checked.
- Browser on isolated `127.0.0.1:18989`, temporary SQLite, worker disabled, no lab credentials: explicit reveal of all four fixtures, correct owner/type/parameter and GET paths; project switch clears IDs, return/reload and login preserve stored data; save existing resource succeeds, hides prior reveal, reread returns `book-A1` and `/books/book-A1`. At 1280×800 no horizontal overflow; reviewed screenshot after fixing narrow resource rows. Evidence: [browser-proof.json](resource-id-20261125/browser-proof.json), [resources-qa.png](resource-id-20261125/resources-qa.png). This is implementer verification, not independent QA. Full landing-page design gate was not applied to this scoped application form change.

## Live web deployment and configuration

Read-only SQL against `deploy-authz-web-1` confirmed project #1 `T18 SSH GET Lab v1` stores four resources before deployment, with identical values after deployment. Actual observed rows are in [runtime-resources.json](resource-id-20261125/runtime-resources.json); the observed mapping below is from SQL, not inferred from alias order:

| Internal row | Stored ID | Owner | Type | Parameter |
|---|---|---|---|---|
| 1 | book-A1 | userA | ssh-book | book_id |
| 2 | book-A2 | userA | ssh-book | book_id |
| 3 | book-B1 | userB | ssh-book | book_id |
| 4 | book-B2 | userB | ssh-book | book_id |

`docker compose --env-file .env -f deploy/compose.yaml build authz-web` and `up -d --no-deps --no-build authz-web` succeeded. Initial compose invocation without `--env-file` failed interpolation before deployment; corrected by explicitly supplying the existing env file. Credential environment parity checked as a boolean, with no values logged. No active runs existed before recreation; run table remained empty afterward. Existing named volume retained, no seed/write applied to live project. `/api/health` returned ok, OpenAPI lists inspection route, unauthenticated inspection returns 401. Live/backend and frontend source/bundle SHA-256 parity confirmed:

- workflow_routes.py: `52c32087a8c3a0bfc972e7374d0035a5cdfbd3b1fe73a6532f1cc00f7ecf6984`
- workflow_schemas.py: `5c11d5c3ec883aa18dd03a948dd240a7d26b0761d49310ad48453b810b644ac9`
- index-Br8HuaaZ.js: `affef035155f4fb2434e81642a4da3eb46d1f8fbbf990467583b31ca1576a9a4`
- index-DLaTqmS6.css: `67b3a263867e12b2f7c033b0b604f07c9adb97c2cf6c1162745ce9e09933587c`

Authenticated browser flow on port 8000 remains NOT_RUN; no real credential was used for browser login. SSH API data/health, owner baselines and cross-owner conclusions remain unverified. No SSH lab traffic, ZAP, disposable mutation, commit or push performed. QA server stopped after evidence collection.
