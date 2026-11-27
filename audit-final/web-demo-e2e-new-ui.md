# E2E with deployed revised UI — 2026-11-13 21:32 Vietnam time

Verdict: BLOCKED for full browser acceptance; deployment PASS. Base HEAD bdbba99, working tree uncommitted.

User authorized revised UI runtime deployment. Lead rebuilt and recreated only authz-web using deploy/compose.yaml; database named volume preserved. No lab service started, scan queued, target request made, commit or push performed.

Commands: docker compose -f deploy/compose.yaml build authz-web (exit 0); docker compose -f deploy/compose.yaml up -d --no-build --no-deps authz-web (exit 0). Build log: /tmp/t18-web-rebuild.log. Dependencies resolved during image build; this is a fresh image, not independent QA of the image.

Runtime health HTTP 200. Browser root references /assets/index-C0TVFM7Q.js. Served asset and local frontend/dist asset SHA256 both f7c76b1cc7d69d59c3bc00b8a4e92ffe4da3ea4bd8b87f89a842e07467b475d5. Container workflow_routes.py and workflow_schemas.py hashes match workspace: de0ffa2b7449078d1cf99c1e6a5652ced9bbae2e6fd1861389ba94a99bb8c06a and 1d906c15c0ef7e960949037f154658124364539085d6a10cf4055e059dba0b7e.

Mounted browser after reload shows login form. Same browser GET /api/projects returns 200 with existing project ID 1: user's server session remains valid. UI initializes authenticated=false in frontend/src/App.tsx:19 with no session restoration; CSRF is memory-only in api.ts. This is a client session-restoration gap, not rejected credentials or proven server expiry. No cookie or credential inspected or logged. Ticket E2E-SESSION-01: restore authenticated UI safely and obtain CSRF through a server-supported mechanism; do not bypass authentication by manipulating React state. Production fix not implemented in this deployment task.

Read-only browser API checks: runs and findings return 200, each empty. GET batch-matrix without target_id returns 422 missing required query parameter; current frontend supplies target_id. With target_id=1 it returns 422: Chưa có resource thuộc mapping GET đã bật để chạy batch. Thus this response is a missing fixture prerequisite, not evidence of old bundle or a route mismatch. Ticket E2E-FIXTURE-01: configure reviewed local GET mapping/resource before batch acceptance.

UI setup, policy/matrix interaction, queue/cancel and findings E2E remain NOT_RUN. R5 NOT_RUN. Existing mock regression PASS does not substitute for these. Automations checked: none.

## Authenticated browser continuation — 2026-11-13 21:32 Vietnam time

Verdict: PARTIAL browser acceptance; full execution BLOCKED. Human sign-in succeeded: mounted Browser displays Logout and revised workflow navigation. No further sign-in needed in this continuation. No credentials/cookies read or logged.

Actual mounted-browser actions and observations:
- Clicked Sinh ma trận read-only: CROSS_IDENTITY actor #1, owner #2, operation #1, DENY / RESOLVED, Policy 2 / v1; OWNER_CONTROL actor #2, owner #2, ALLOW / RESOLVED, Policy 1 / v1. Both show identity.unverified_precheck, correctly not runtime verification.
- Clicked Thêm mapping batch for GET /books/{book_id} and resource type book. Persisted BATCH ENABLED and success notice observed. This is a web configuration write; no target request. Mapping left enabled for the next acceptance attempt.
- Batch preview loaded: 2 identities, 1 resource-operation, 2 actor cases, 2 verification + 1 owner baseline + 2 actor requests = 5/100 planned attempts. Queue button enabled. Missing-mapping prerequisite resolved.
- Selected existing policy #1 in editor, then changed subject selector to Role: identity field disappeared, Role áp dụng appeared. No policy save submitted, so this checks editor interaction only, not create/update persistence.
- Comparison displays NOT_RUN/NO_TIMING for unavailable verified sources; no benchmark invented.

Execution gate: configured target is http://100.106.64.21:5003. README documents this as Controlled BOLA Lab, but current host interface inspection shows a different Tailscale address; target is not loopback or a current host address. The standing local-lab-only scope is therefore not established for this endpoint. No queue, verify-identity, test-target or bridge action performed. Do not claim the documented remote lab is a third-party production service; the issue is scope/locality verification.

Queue/cancel, live owner baseline, run-scoped findings/evidence and full browser execution remain NOT_RUN. R5 NOT_RUN. Session restoration gap remains open separately; no reload was performed in this authenticated continuation. Only two stored identities share role user, so 3/5-role gate remains unmet. No source edits/rebuild/restart/lab start/commit/push. Related automations checked: none.
