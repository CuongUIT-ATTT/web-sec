# E2E retry — 2026-11-13

Base HEAD: bdbba9933ca057cb2247c3a1de9b3ee239c452bd; working tree uncommitted.

Status: BLOCKED at administrator sign-in, not an E2E PASS.

Mounted browser opened http://127.0.0.1:8000/ successfully and displayed the administrator password form. Browser is operational. No saved login is available. User sign-in is required before authenticated UI checks. No credentials read or printed.

Runtime listener exists at loopback port 8000. Its served asset/source parity is not yet established; source main.py serves backend/frontend_dist, whereas recent frontend builds are in frontend/dist. Verify deployed assets before accepting the UI revision.

Setup/matrix/queue/results/findings/browser regressions remain NOT_RUN in this retry. R5 remains NOT_RUN. No runtime restarted, lab started, scan queued or target state changed. No related automations exist.

Prior independent mock regression evidence: web-demo-stale-response-recheck.md (15 frontend tests, lint/build PASS); this does not substitute for E2E.

## Sign-in continuation — 2026-11-13 21:20 Vietnam time

Status: BLOCKED; E2E not accepted. Browser initially showed an authenticated control room with existing project, but a subsequent fresh navigation returned the login form. The saved-login attempt reported rejection; no repeated submission was made. Human sign-in requested again. No credentials were read or recorded.

Observed authenticated page lacked the current workflow navigation and role/resource policy controls. GET /api/projects/1/batch-matrix reported HTTP 422; clicking matrix generation produced no visible change. These are runtime observations, not yet a diagnosed source defect. Served asset parity remains unverified: frontend/dist contains index-C0TVFM7Q.js, while backend/frontend_dist is absent in this checkout; the running process uses backend.app.server:app. Do not accept this runtime as the revised source until deployment parity is established.

No queue, lab execution, target writes, runtime restart or deployment was performed. Full authenticated E2E and R5 remain NOT_RUN. No related automations exist.

## Human sign-in confirmation recheck — 2026-11-13 21:20 Vietnam time

Verdict: BLOCKED for acceptance of the revised UI. Initial mounted-browser snapshot confirmed an authenticated view (Logout and existing project setup visible). Thus the human sign-in step succeeded at the UI level. No secret fields were read. The page reported GET /api/projects/1/batch-matrix HTTP 422 and queue was disabled.

A fresh browser reload returned the login form. This alone does not prove server session expiry: current source initializes authenticated=false and keeps CSRF only in module memory. No password retry or credential request was made.

Read-only asset parity check independently confirms deployment mismatch: live root references /assets/index-ByQ5MMj0.js (SHA256 ef8de72b49a892fbfb32cbfe3b5f3ada35e2aecb877e731635d58bb5e9ed3db1); local frontend/dist references index-C0TVFM7Q.js (SHA256 f7c76b1cc7d69d59c3bc00b8a4e92ffe4da3ea4bd8b87f89a842e07467b475d5). Commands: curl -fsS local root, curl asset piped to sha256sum, sha256sum local asset; exit 0. HEAD remains bdbba9933ca057cb2247c3a1de9b3ee239c452bd, working tree uncommitted. Browser snapshot also lacks revised workflow navigation and role policy controls. The 422 is an observed old-runtime defect, not attributed to revised source.

Next prerequisite: deploy the reviewed frontend/backend together under the project's explicit runtime-change approval rule, verify asset parity, then repeat authenticated browser checks. No deployment/restart, target call, queue, lab execution, or target write performed. Full revised-flow E2E and R5 remain NOT_RUN. Related automations checked: none.
