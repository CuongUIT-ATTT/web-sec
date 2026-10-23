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
python3 -I week2/main.py
python3 -I week3/run_week3.py
```

Run dependency-free unit tests after installation (or with the package otherwise on `sys.path`):

```bash
.venv/bin/python -I -m unittest discover -s tests -v
```

The packaging configuration is in `pyproject.toml`; no `requirements.txt` is provided because no non-standard-library runtime package is required.

The latest completed packaged rerun recorded 12 read-only known-fixture cases in **2032.298 ms**, including preflight and the configured 150 ms inter-case delay. This host/Docker-specific pipeline measurement is not a general benchmark and does not replace a human Postman/Burp/stopwatch measurement. See `results/rerun-week3/week3_script_timing.json`.

## Week 2 safe authorization pipeline

The Week 2 implementation uses only the Python standard library. It reads the Week 1 OpenAPI spec, role configuration, and ownership CSV; creates a fixture-backed test matrix; and runs read-only checks only.

```bash
python3 -I week2/main.py --base-url http://127.0.0.1:5000
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

Run the unit tests without contacting Docker or the API:

```bash
python3 -I -m unittest discover -s tests -v
```

## Week 3 verification and comparison

Week 3 independently re-fetches owner baselines and cross-user book responses; it does not reuse the Week 2 comparator evidence to claim confirmation. It still permits only local `GET` requests to known fixtures.

```bash
python3 -I week3/run_week3.py
```

Generated artifacts include independent verification, classification, timing, and a comparison table:

- `results/week3_manual_verification.json`
- `results/week3_findings.json`
- `results/week3_script_timing.json`
- `results/week3_comparison.json`
- `results/week3_manual_worksheet.md`

The seven manual Postman cases are functionally complete and independently confirm two user-to-user BOLA cases. Stopwatch timing was intentionally not measured; `results/week3_manual_worksheet.md` uses `—` and Week 4 reports this accurately as `COMPLETED_NO_TIMING`. Automated timing is never substituted for a human-tool timing metric.

The historical ZAP artifact remains `NOT_RUN`; it provides no scanner finding, absence-of-finding, or false-negative result. The Week 4 implementation now requires a manually reviewed imported ZAP Context with exact rules/users plus fail-closed paginated HTTP-history containment. Site Tree parent nodes are diagnostics only, never standalone scan evidence. See `docs/week-4-report.md` for the private Context workflow.

## Week 4 — BFLA disposable, ZAP evaluation and final comparison

Week 4 adds BFLA real execution on a disposable VAmPI container, ZAP Access Control scan scaffolding, and a final comparison of all methods.

### BFLA guardrail and findings

`week4/bfla_executor.py` adds a defense-in-depth guardrail (`assert_disposable_target()`) that rejects known fixture usernames (`userA`, `userB`, `admin`, `name1`, `name2`) and accepts only disposable patterns (`bfla_disposable_*` or `bfla-<run_id>-*`).

```bash
# Generate Week 4 BFLA findings from an existing disposable run:
python3 -I week4/run_week4.py --run-id bf1a2026 --skip-zap
```

### ZAP Access Control (verified imported Context)

ZAP allowlist v2 (`zap/allowlist-v2.json`) declares five safe GET URLs. The runner imports a manually reviewed, private mode-`0600` ZAP Context containing exactly `admin`, `userA`, and `userB` plus reviewed Access Rules. It validates a non-secret fingerprint attestation and paginated actual HTTP history before and after the scan. Site Tree parent nodes are diagnostics only.

```fish
# Requires the reviewed private files and a fresh loopback-only ZAP daemon.
python3 -I week4/run_week4.py \
  --run-id bf1a2026 \
  --zap-api-key '<local-zap-api-key>' \
  --zap-context zap/private/vampi-safe-authz.context \
  --zap-context-in-container /zap/context/vampi-safe-authz.context \
  --zap-attestation zap/imported-context-attestation.json \
  --zap-html-on-host zap/run-output/access-control.html \
  --zap-html-in-container /zap/output/access-control.html
```

See `docs/week-4-report.md` for the Desktop review/export and Fish Docker commands. Until that validated real run produces a new redacted report, ZAP remains `NOT_RUN`.

### Manual measurement

Seven manual Postman cases confirmed 2 BOLA user-to-user findings, matching the script results. See `results/week3_manual_worksheet.md`.

### Final comparison

`results/week4_comparison_final.json` summarizes all four methods: custom script (2 BOLA confirmed), manual Postman (2 BOLA confirmed), ZAP (NOT_RUN), and BFLA disposable (DENIED_CONTROL).

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
