# Recovered S01 browser E2E — 2026-11-13 21:46 Vietnam

Lead verdict: PASS for observed live GET batch and finding display; overall acceptance PARTIAL, independent QA pending.

User explicitly approved LAB-RECOVER-01. Base HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd; existing uncommitted changes preserved. No production source edits, commit, reset, deletion, active ZAP or destructive HTTP calls.

On cuong@192.168.1.12, created separate private state /home/cuong/VAmPI/bola-lab-state-e2e-20261113-2148, scenario S01, token TTL 14400 seconds. Controller init and validate exited 0. Existing state and stale lock untouched. Started user systemd unit t18-bola-e2e-20261113.service bound specifically to 100.106.64.21:5003 with allowed client 100.68.153.87. No firewall changes; independent denied-source isolation was not tested. Host GET /health returned ready; web worker subsequently reached target successfully.

Transferred only userA/userB issued credentials through SSH in memory into authenticated write-only identity update API; no credential or private state file saved locally or printed. Both verification API results: authentication_passed=true, principal_matched=true, principal_confirmed=true, COMPLETED_RESPONSE. Existing Browser login remained usable.

Mounted Browser: clicked Queue all selected GET mappings once; run #2 reached COMPLETED. Visible summary: planned 5, transport 5, responses 5, scope 0, errors 0, cancelled 0. Opened results: 2 cases, 1 finding group.

| case_id | execution | conclusion | HTTP | policy/evidence |
|---|---|---|---|---|
| operation:1:resource:1:actor:1 | COMPLETED_RESPONSE | CONFIRMED_VIOLATION | 200 | #2 v1 DENY RESOLVED; evidence.restricted_fields_match_owner |
| operation:1:resource:1:actor:2 | COMPLETED_RESPONSE | POLICY_CONSISTENT_CASE | 200 | policy.allow_observed |

Opened first case evidence in Browser: owner control valid=true; fresh owner response COMPLETED_RESPONSE HTTP 200; actor target match/restricted fields match owner=true/true. Finding GET /books/{book_id}, policy #2 v1, one reproduction. Fixture book-B1 owned by userB; actor userA is denied by explicit policy. Scenario S01 is the controlled disclosure fixture. Selected nonsecret columns queried read-only from container SQLite confirmed both persisted run #2 case conclusions and reason codes match Browser. No raw response or marker exported. Earlier run #1 remains preserved as NETWORK_ERROR evidence.

PASS scope: successful GET queue/worker, principal verification, fresh owner baseline, policy-aware BOLA finding, allowed owner case and live result display. Not a full project acceptance: only two identities with one role user; 3/5-role gate unmet. Cancel/duplicate-click E2E NOT_RUN; independent QA pending; BFLA not assessed; R5 manual/ZAP comparison and R8 NOT_RUN. No comparison timings invented. Related automations checked: none. Lab remains running under the approved recovery, credentials expire after four hours; service has no automatic stop configured.
