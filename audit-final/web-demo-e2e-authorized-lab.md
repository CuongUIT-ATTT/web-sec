# E2E — 2026-11-13 21:34 Vietnam time

Verdict: PARTIAL; live authorization acceptance BLOCKED by connection refusal.

User explicitly confirmed target 100.106.64.21:5003 is in approved lab scope and authorized E2E. Base HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd; working tree remains uncommitted. Existing authenticated mounted Browser at http://127.0.0.1:8000/ used without reload or credential inspection.

Browser: clicked Queue all selected GET mappings once, then Xem kết quả. Run #1 reached COMPLETED. UI summary: planned 5, transport 5, responses 0, scope 0, errors 5, cancelled 0. Once asynchronous results loaded, UI displayed 2 cases and 0 finding groups; both cases NETWORK_ERROR / NOT_EVALUATED, no HTTP status. Case IDs operation:1:resource:1:actor:1 and operation:1:resource:1:actor:2. No BOLA verdict inferred from completion or absence of findings.

Read-only SQLite cross-check in authz-web container: run 1 COMPLETED; both persisted cases match UI with reason execution.network_error and null HTTP status; two batch claims. Numeric summary observed directly in Browser. No raw responses, credentials, snapshot or token read/exported.

Diagnostic socket.create_connection((100.106.64.21,5003),5) from both host and authz-web container returned ConnectionRefusedError [Errno 111]. Both diagnostic shell commands exited 0 because exception was handled and reported; this is a negative connectivity result, not successful connection. This proves refusal at test time, not which service/firewall component caused it.

Queue, worker completion, bounded summary and run-scoped error rendering: PASS for observed error path. Successful principal verification, fresh owner baseline, positive/negative authorization, live findings/evidence: BLOCKED. Cancel and duplicate-click browser scenarios NOT_RUN; no unnecessary second run. Only two identities with role user, so 3/5-role gate unmet. R5 manual/ZAP NOT_RUN. No lab start, source change, deployment, commit, push, active ZAP or destructive API call. Runtime mutation lock released after terminal run. Related automations checked: none.

Next prerequisite: restore the approved lab listener/reachability on port 5003, then repeat successful-response E2E. No full acceptance or COMPLETE claim.
