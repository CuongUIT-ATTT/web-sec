# SSH lab diagnosis

Checked: 2026-11-13T21:44:20.944637+07:00. Verdict: E2E BLOCKED; SSH access PASS.

Local repository HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd; existing uncommitted changes preserved.

Authenticated as cuong at 192.168.1.12 using the supplied secure file without printing or copying its contents. Host cuong-dell-ubuntu owns Tailscale address 100.106.64.21. Remote ss -lnt confirms no port 5003 listener. docker command is unavailable, which does not establish absence of other runtimes.

Existing controlled lab: /home/cuong/VAmPI, remote HEAD 534bca05268e3ceb9d273b285bb5fc572cd62a72, git status --short empty. Existing Flask virtual environment imports successfully. Reviewed bola_lab_app.py, server.py, network.py and docs/bola-lab-operator-guide.vi.md. Public surface is GET-only; application has bounded peer allowlisting.

Read only selected nonsecret manifest fields: scenario S01, TTL 360000 seconds, calculated expiry already passed. Existing server.lock refers to a nonexistent PID. No tokens, signing secrets, markers, answers or database contents exported. Remote diagnostic commands completed with REMOTE_EXIT 0 except an earlier optional service-name search (1, no matching service); not interpreted as a successful lab start.

No service start, reset, lock removal, token rotation, firewall edit, dependency installation or additional E2E queue performed. Existing run #1 remains NETWORK_ERROR / NOT_EVALUATED. R5 NOT_RUN.

Concrete proposed recovery ticket LAB-RECOVER-01: preserve all existing private state; prepare a separate S01 state directory on the lab host; start the existing GET-only application bound to 100.106.64.21:5003 with only the approved tester source 100.68.153.87 allowed; securely update the two existing web identities with newly issued credentials; verify health and principals; rerun the existing GET batch and record case/run evidence. Requires explicit approval for new lab state and credential replacement under the project standing restriction. No production code change, destructive HTTP call or ZAP active scan included.
