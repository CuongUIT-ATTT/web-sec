# VAmPI Week 1 Lab

This directory contains artifacts for an **authorized, isolated VAmPI Docker lab**. The API is published only to `127.0.0.1:5000`; it is not intended for testing third-party or production systems.

## Current lab

- Container: `vampi-week1`
- Image: `vampi-week1:local`
- API: <http://127.0.0.1:5000/>
- Swagger UI: <http://127.0.0.1:5000/ui/>
- Vulnerable mode: `vulnerable=1`
- Token lifetime: 3600 seconds

The database was initialized with `GET /createdb` before creating Week 1 accounts and fixtures.

## Deliverables

| File | Purpose | Sensitivity |
| --- | --- | --- |
| `vampi_spec.json` | OpenAPI specification fetched from the running local API | Local lab metadata |
| `roles_config.json` | Bearer tokens for `admin`, `userA`, and `userB` | Secret — mode `0600`, excluded from version control |
| `ownership.csv` | Resource-to-owner mapping for the Week 2 test matrix | Local lab metadata |

The VAmPI source is kept in `VAmPI-source/` as downloaded third-party code. Treat it as untrusted and do not run Python directly from that directory.

## Safe operations

```bash
# Verify lab status
docker ps --filter name=^/vampi-week1$

# View recent container output
docker logs --tail 50 vampi-week1

# Stop without deleting the image or lab artifacts
docker stop vampi-week1

# Start the stopped lab again
docker start vampi-week1
```

All Week 2 automation must restrict its target to `http://127.0.0.1:5000`, use only the resource identifiers listed in `ownership.csv`, and avoid writing bearer tokens to output.

## Week 4 packaged CLI

The project is packaged as `vampi-authz-lab`. It has **no third-party Python runtime dependency** and is intentionally a VAmPI-local teaching-lab tool, not a general-purpose scanner.

Install it in an isolated local environment from this project directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
```

The console command and module entry point expose the same subcommands:

```bash
# Validate inputs only; this does not contact Docker or the API.
.venv/bin/vampi-authz-lab check-inputs

# Execute the safe Week 2 read-only matrix.
.venv/bin/vampi-authz-lab run

# Independently verify known book fixtures without rerunning the Week 2 matrix.
.venv/bin/vampi-authz-lab verify

# Run the timed read-only pipeline and then independent Week 3 verification.
.venv/bin/vampi-authz-lab week3

# Validate a reviewed ZAP GET-only scope; this does not start ZAP or send requests.
.venv/bin/vampi-authz-lab check-zap-allowlist

# Preserve historical artifacts by writing a new packaged rerun directory.
.venv/bin/vampi-authz-lab week3 --output-dir results/rerun-week3

# Equivalent module entry point.
.venv/bin/python -m vampi_authz_lab check-inputs
```

Every subcommand accepts `--spec`, `--roles-config`, `--ownership`, and `--output-dir` for local artifact paths. `--base-url` remains available only to make the safety check explicit: the program accepts **only** `http://127.0.0.1:5000`; all other target values stop safely before a request is sent.

`ownership.csv` is the canonical safety-critical input. It must contain these columns:

```text
resource_type,resource_id,owner_role,owner_username,path_template
```

`results/ownership_map.json` is a redacted exported artifact, not an interchangeable matrix input. `roles_config.json` remains secret, is excluded by `.gitignore`, and must remain mode `0600`.

Existing source-checkout commands remain supported for compatibility:

```bash
.venv/bin/python -I week2/main.py
.venv/bin/python -I week3/run_week3.py
```

Run dependency-free unit tests after installation. Because `-I` excludes the checkout from `sys.path`, use the installed project virtualenv:

```bash
.venv/bin/python -I -m unittest discover -s tests -v
```

The current complete suite contains **128 tests**. Historical report counts are stage-specific and not interchangeable: Week 2 recorded 13 tests, Week 3 recorded 19 before later BFLA/ZAP work, and the pre-quiescence Week 4 regression suite recorded 87.

The packaging configuration is in `pyproject.toml`; no `requirements.txt` is provided because no non-standard-library runtime package is required.

The latest completed packaged rerun recorded 12 read-only known-fixture cases in **2032.298 ms**, including preflight and the configured 150 ms inter-case delay. This host/Docker-specific pipeline measurement is not a general benchmark and does not replace a human Postman/Burp/stopwatch measurement. See `results/rerun-week3/week3_script_timing.json`.

## Week 2 safe authorization pipeline

The Week 2 implementation uses only the Python standard library. It reads the Week 1 OpenAPI spec, role configuration, and ownership CSV; creates a fixture-backed test matrix; and runs read-only checks only.

```bash
.venv/bin/python -I week2/main.py --base-url http://127.0.0.1:5000
```

Before testing, the pipeline verifies VAmPI vulnerable mode, every role token via `GET /me`, and each owner’s known book fixture. It then writes redacted artifacts to `results/`:

- `endpoint_inventory.json`
- `ownership_map.json`
- `test_matrix.json`
- `preflight.json`
- `raw_results.json`
- `final_report.json`

Safety rules enforced by the runner:

- The URL must be exactly `http://127.0.0.1:5000`.
- Identifiers come only from `ownership.csv`; no enumeration or fuzzing occurs.
- `POST`, `PUT`, `PATCH`, and `DELETE` are disabled.
- `GET /createdb` is permanently blocked because it resets the lab database.
- Request headers and bearer tokens are never persisted in output files.

Run the unit tests without contacting Docker or the API. Because `-I` excludes the checkout from `sys.path`, use the project virtual environment after installing the package; a system `python3 -I` cannot import the packaged modules from the checkout:

```bash
.venv/bin/python -I -m unittest discover -s tests -v
```

## Week 3 verification and comparison

Week 3 independently re-fetches owner baselines and cross-user book responses; it does not reuse the Week 2 comparator evidence to claim confirmation. It still permits only local `GET` requests to known fixtures.

```bash
.venv/bin/python -I week3/run_week3.py
```

Generated artifacts include independent verification, classification, timing, and a comparison table:

- `results/week3_manual_verification.json`
- `results/week3_findings.json`
- `results/week3_script_timing.json`
- `results/week3_comparison.json`
- `results/week3_manual_worksheet.md`

The seven manual Postman cases are functionally complete and independently confirm two user-to-user BOLA cases. Stopwatch timing was intentionally not measured; `results/week3_manual_worksheet.md` uses `—` and Week 4 reports this accurately as `COMPLETED_NO_TIMING`. Automated timing is never substituted for a human-tool timing metric.

The current ZAP artifact is `COMPLETED` after a reviewed local Desktop run: 15 result rows (five fixtures × three users) and five scanner-labeled `ILLEGAL` rows. Two are **owner** book accesses (`userA` on book A and `userB` on book B), not the two confirmed cross-user BOLA cases; the remaining three are `/me` rows. These are rule-alignment discrepancies requiring Context/Access-Rule review, not new BOLA findings or independent confirmation of the two known BOLA cases. Because the redacted artifact persists only `ILLEGAL` rows, its absence of an admin-book finding does not prove a `VALID` result. The Week 4 implementation requires a manually reviewed imported ZAP Context with exact rules/users plus fail-closed paginated HTTP-history containment. Site Tree parent nodes are diagnostics only, never standalone scan evidence. See `docs/week-4-report.md` for the private Context workflow.

## Week 4 — BFLA disposable, ZAP evaluation and final comparison

Week 4 adds BFLA real execution on a disposable VAmPI container, ZAP Access Control scan scaffolding, and a final comparison of all methods.

### BFLA guardrail and findings

`week4/bfla_executor.py` adds a defense-in-depth guardrail (`assert_disposable_target()`) that rejects known fixture usernames (`userA`, `userB`, `admin`, `name1`, `name2`) and accepts only disposable patterns (`bfla_disposable_*` or `bfla-<run_id>-*`).

```bash
# Generate Week 4 BFLA findings from an existing disposable run:
.venv/bin/python -I week4/run_week4.py --run-id bf1a2026 --skip-zap
```

### ZAP Access Control (reviewed Context)

ZAP allowlist v2 (`zap/allowlist-v2.json`) declares five safe GET URLs. Every mode validates the local private mode-`0600` Context against its non-secret fingerprint attestation, then validates exact Context metadata, users, explicit successful ZAP poll state, and paginated actual HTTP history before and after the scan. The state gate accepts only the reviewed legacy or current Desktop response contract and never exports state payloads. Site Tree parent nodes are diagnostics only.

**Docker import mode** (the default) imports the Context from an explicit, read-only ZAP-visible path:

```fish
.venv/bin/python -I week4/run_week4.py \
  --run-id bf1a2026 \
  --zap-context-mode import \
  --zap-api-key "$ZAP_KEY" \
  --zap-context zap/private/vampi-safe-authz.context \
  --zap-context-in-container /zap/context/vampi-safe-authz.context \
  --zap-attestation zap/imported-context-attestation.json \
  --zap-html-on-host zap/run-output/access-control.html \
  --zap-html-in-container /zap/output/access-control.html
```

**Preloaded ZAP Desktop mode** is explicit. First manually load and review `vampi-safe-authz` in the same fresh Desktop session; the runner does not import, repair, or modify it:

```fish
# Copy the key from the local ZAP GUI; keep it only in this shell session.
set -lx ZAP_KEY '<key-from-zap-gui>'

set -l PROJECT (pwd)
.venv/bin/python -I week4/run_week4.py \
  --run-id bf1a2026 \
  --zap-context-mode preloaded-desktop \
  --zap-api-key "$ZAP_KEY" \
  --zap-context "$PROJECT/zap/private/vampi-safe-authz.context" \
  --zap-attestation "$PROJECT/zap/imported-context-attestation.json" \
  --zap-html-on-host "$PROJECT/zap/run-output/access-control.html" \
  --zap-html-in-container "$PROJECT/zap/run-output/access-control.html"
```

Preloaded mode never transfers Context data over the API; the local export remains only for private fingerprint validation. No mode enables file transfer, edits Access Rules, or broadens the five-GET scope. The disposable HTML-report path must be an absolute ZAP-visible path, distinct from both JSON artifact paths, and must not exist before a run; the runner owns and removes only the report it requested.

After a Desktop restart, use the explicit **read-only bootstrap** first. It verifies only reviewed Context/user metadata and emits no target request, seed, scan, report, or history mutation:

```fish
set -l PROJECT (pwd)
.venv/bin/python -I week4/run_week4.py \
  --run-id bf1a2026 \
  --zap-bootstrap-only \
  --zap-context-mode preloaded-desktop \
  --zap-api-key "$ZAP_KEY" \
  --zap-context "$PROJECT/zap/private/vampi-safe-authz.context" \
  --zap-attestation "$PROJECT/zap/imported-context-attestation.json"
```

When it returns `BOOTSTRAP_REQUIRES_OPERATOR_AUTH_AND_QUIESCE`, use ZAP Desktop—not the runner/API—to authenticate and poll each reviewed user, then stop browser/proxy/scanner traffic. Do not use `New Session`, automated node deletion, global Replacer rules, or copy token/header values. The normal preloaded command independently requires every user to remain authenticated, then requires two equal target-scoped Core message counts one second apart (retrying for no more than ten seconds). A quiescence timeout returns `NOT_RUN` before baseline capture, seeding, or scanning. Once quiesced, it captures the Core API target history as a private post-auth baseline, proves the seed delta has exactly one of each five fixed GETs, and requires every later scan delta to remain allowlisted. An empty History or Sites view is not containment evidence in ZAP 2.17: authentication/poll records can remain Core-API-visible while Desktop omits them. Counts, baseline identities, raw history, credentials, headers, tokens, and bodies are never exported. See `docs/week-4-report.md` for the detailed review process. The validated local run produced the current redacted `COMPLETED` artifact.

### Manual measurement

Seven manual Postman cases confirmed 2 BOLA user-to-user findings, matching the script results. See `results/week3_manual_worksheet.md`.

### Final comparison

`results/week4_comparison_final.json` summarizes all four methods: custom script (2 BOLA confirmed), manual Postman (2 BOLA confirmed), ZAP (COMPLETED: 15 reviewed rows, 5 scanner-labeled rule anomalies), and BFLA disposable (DENIED_CONTROL). ZAP's output does not independently confirm either cross-user BOLA case and is not interchangeable with the script/Postman sensitive-field evidence.

### Reports

- `docs/week-3-report.md` — Week 3 report (Vietnamese)
- `docs/week-4-report.md` — Week 4 report (Vietnamese)
- `docs/final-report-draft.md` — Final report with full reproduction guide (Vietnamese)

## Disposable BFLA authorization control

`vampi-authz-lab` remains permanently read-only: it cannot be used for BFLA mutation testing. The opt-in `vampi-bfla-disposable` command is a separate, fixed-scope workflow for one local VAmPI deployment at `http://127.0.0.1:5003`. It cannot target the shared `vampi-week1` lab, accepts no target/method/path override, uses a one-run manifest, and tears down only its own Compose project and SQLite volume.

The workflow may use `GET /createdb` only during preparation of its own newly-created disposable database. It never contacts the shared Week 1 origin and never relaxes the `week2`/`week3` runner restrictions. Durable BFLA artifacts contain only bounded status/survival outcomes, never passwords, bearer tokens, authorization headers, or response bodies.

```bash
# After installing the package, choose a new lowercase 8–32-character run ID.
.venv/bin/vampi-bfla-disposable create-manifest --run-id a1b2c3d4

# Preflight is read-only: it attests the running shared lab, an empty matching
# Compose project, a free disposable loopback port, and the disposable image.
.venv/bin/vampi-bfla-disposable preflight --run-id a1b2c3d4

# Compose lifecycle is explicit and must use the matching project name.
docker compose --project-name vampi-bfla-a1b2c3d4 --file bfla-disposable/compose.yaml up --detach --wait --wait-timeout 60

.venv/bin/vampi-bfla-disposable prepare --run-id a1b2c3d4
.venv/bin/vampi-bfla-disposable execute --run-id a1b2c3d4
.venv/bin/vampi-bfla-disposable teardown --run-id a1b2c3d4
```

`preflight` is a required, immutable attestation stage for a new run ID. `prepare` and `execute` re-check its receipt, the shared-lab snapshot, and the disposable image identity before any API action; `teardown` reloads the receipt when available and records fresh shared-lab snapshots while removing only the scoped project. Always run `teardown`, including if `execute` reports an unexpected authorization success. The completed evidence run is stored in `results/bfla-disposable/bf1a2026/` and records `DENIED_CONTROL` plus `TEARDOWN_COMPLETE`.
