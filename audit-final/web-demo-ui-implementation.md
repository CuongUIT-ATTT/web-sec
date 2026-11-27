# UI-WEB-01 — integration status

2026-11-13. Base HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd; uncommitted working tree.

Lead implemented frontend/src/App.tsx, api.ts, styles.css after Frontend Engineer returned ownership without changes.

Implemented: workflow anchor navigation; policy identity XOR role with resource scope preserved on edit; matrix owner/operation/resolved decision/policy/version; run-scoped findings request; explicit evidence allowlist display and unavailable fallback; synchronous queue/cancel mutex for batch; bridge queue mutex; bounded non-overlapping polling (300 attempts, 2s delay) with cleanup; stale preview/results guards; project refresh generation guard; comparison placeholders explicitly NOT_RUN/NO_TIMING with missing-source explanation. Preserved API transport/CSRF and GET target scope. No CLI imports, ZAP or BFLA execution.

Verification by Lead: npm --prefix frontend test: 3 passed exit 0; npm --prefix frontend run build: exit 0; npm --prefix frontend run lint: exit 0 after final edits; git diff --check exit 0. .venv/bin/python -m pytest -q backend/tests: 140 passed, 1 warning, 15.89s, exit 0. Final polling/project guards were added after test/build, so independent QA must rerun frontend checks.

Limits: anchor navigation is not the complete wizard/page-container redesign; matrix filtering/sorting and comparison import/export remain pending. Existing tests do not cover new policy/evidence behavior. Browser/live demo NOT_RUN in this integration turn. Earlier Chrome blocker not independently retested. No claim that R5 or demo acceptance is complete. Skill design-taste-frontend consulted; visual browser gate NOT_RUN. No dependencies installed, commit/push/reset, or external API scan.
