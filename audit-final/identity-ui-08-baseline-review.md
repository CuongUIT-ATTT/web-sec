# IDENTITY-UI-08 — Independent baseline/provenance review

Reviewer: T18 BOLA Evaluator. Date: 2026-11-16 (Vietnam time).
Scope verdict: **PARTIAL**. Static provenance review and independent comparison of existing redacted artifacts completed; original screenshot discrepancy remains **INCONCLUSIVE**. This is not runtime QA or approval of the complete redesign.

## Boundaries and provenance

HEAD observed: `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; working tree contains extensive pre-existing tracked/untracked changes. No production edits, application/lab execution, persistent DB access, Run #2 access, external traffic, commit or push. Only this report was written. No automations exist for this reviewer.

Read sources: authorization_model.py, authorization_execution.py, authorization_routes.py, authorization_runner.py, run_snapshot.py, demo_presentation.py, AuthorizationWorkflow.tsx and regression test source. Read prior mainweb-demo-07 QA report and redacted preview/results artifacts. The old PDFs were previously transcribed under results/identity-ui-08; original persistent run snapshot is unavailable within authorized scope.

## Baseline selection and execution

1. `backend/app/services/authorization_model.py:181-184`: only eligible identities with policy ALLOW enter baseline candidates. Resource owner is preferred if eligible and allowed; otherwise lowest allowed identity ID. A non-owner baseline can therefore be intentional. For functions, owner is absent and authorized identity is selected. Do not interpret baseline as always the resource owner.
2. `backend/app/services/authorization_execution.py:19-27`: queue regenerates preview and deep-copies selected cases; revision checks configuration revision. This fixes a queue-time snapshot, which need not be an earlier screenshot preview. Case ID alone does not identify a run or revision.
3. `backend/app/workers/authorization_runner.py:53-67`: baseline request uses the snapshot baseline ID; cache key includes operation/resource/baseline ID. No runtime fallback to current configuration was found.
4. Runner lines 83-95 persists the baseline ID associated with the response and redacted comparison booleans. Lines 96-100 preserve completed case evidence before subsequent requests.
5. `backend/app/api/authorization_routes.py:129-158`: planned baseline comes from snapshot case; actual baseline comes from persisted result evidence. Missing observed ID stays NOT_OBSERVED, never silently filled from planned/current config. Frontend lines 99-100 warns when actual and planned differ.

**Original #3 versus #5: INCONCLUSIVE, not a demonstrated runner defect.** Establishing a cause requires the original matching run/case snapshot and observed evidence, together with the preview revision. Those original records were not opened. An authorized non-owner fallback explains how a different baseline can be selected in general; it does not prove what happened in these screenshots. New synthetic artifacts cannot resolve the provenance of the original persistent run.

## Independent artifact checks performed in this review

Local Python JSON comparison, exit 0; no requests or database use:

| Fixture/artifact directory | Run | Cases joined on case_id | Preview baseline = result planned baseline | Policy revision equal | Observed baseline available / equal planned |
| --- | --- | --- | --- | --- | --- |
| results/mainweb-demo-07 | 1 | 12 | 12/12 | yes | unavailable in old public DTO |
| results/mainweb-demo-07-qa | 1 | 12 | 12/12 | yes | unavailable in old public DTO |
| results/identity-ui-08 | 1 | 12 | 12/12 | yes | 12/12 available, 12/12 equal |

For exact case IDs/revisions and result references see each directory's preview/results JSON (`docker-preview.json`/`docker-results.json`; QA uses `preview.json`/`results.json`). Fixture is the synthetic GET demo, not original persistent Run #2. This comparison verifies consistency of saved artifacts, not fresh execution or independent server receipts. Old public DTO baseline_identity_id is the snapshot planned ID, so its match is not proof of observed baseline.

## Immutable labels and compatibility

- `authorization_execution.py:49-56` captures display name/role plus resource alias and ownership metadata at queue time. Names are not fetched from mutable identities in results; rename/deletion does not relabel a populated snapshot.
- `authorization_routes.py:120-128` uses immutable labels and falls back to legacy snapshot roles when names are absent; source is LEGACY_UNAVAILABLE. Missing labels remain explicit.
- Resource labels are synthetic `resource-{id}` aliases, not external IDs or private resource values. Method/path and owner derive from saved case metadata. Raw response bodies, tokens and private evidence values are not added by these view models.
- `test_authorization_execution.py:357-394` covers rename, legacy absence, deliberately divergent observed baseline, NOT_OBSERVED remaining rows, redaction sentinel and exact snapshot preservation. This review read the test; it did not execute it.

## Concrete follow-ups before acceptance

**F1 — medium, legacy Run summary drops available role:** `backend/app/services/demo_presentation.py:49-52` only reads display_metadata roles. Unlike results identity_label at authorization_routes.py:123-128, it does not fall back to immutable snapshot.identities roles. Thus a legacy run with known historical role shows ID/missing label in Run but ID/role in Results. Strictly necessary fix: use the same immutable role fallback in public_snapshot; never query current identities. Add focused assertion for legacy Run case summaries.

**F2 — test coverage gap:** the new rename/legacy test does not delete identities or test partially missing display metadata. Add isolated tests that omit one metadata entry and change/remove current identity metadata while keeping the snapshot unchanged; assert actor/owner/planned/actual labels and role fallback in both Run and Results. Do not delete persistent records.

**F3 — evidence gap:** original screenshot baseline discrepancy remains unresolved. Acceptance report must retain this uncertainty and distinguish synthetic observed consistency from original-run verification. No claim that #3 changed to #5 because of policy or a different snapshot is currently justified.

Existing logs report 240 backend tests and 63 frontend tests passed, plus 87 focused backend tests; these are implementer artifacts, not this reviewer's test executions. Full UI/browser/responsive acceptance, cancellation runtime, large result sets and persistent preservation are outside this read-only review and remain for independent QA. No evaluation/policy/matrix semantics change is proposed.
