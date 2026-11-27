# Execution manifest — QA CMP07 adapter

Python 3.14.8, pytest 9.2.0, pytest-asyncio 1.4.1.post1; pytest-subtests package không cài riêng (pytest hiện tại vẫn chạy 392 subtests). CWD repository hiện tại; timestamps UTC+07. Không thấy AGENTS.md tại root và các thư mục cha đã kiểm. Không truy cập lab/context/credential/process runtime; lab image digest và runtime fixture snapshot **UNKNOWN**, không suy từ fixture metadata.

OpenAPI `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json`: SHA-256 `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b`. Ownership `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f`. Fixture bundle metadata `a02f42b62ba6e6efa08cff2701c0fef3b62722770c0fa1bba1573d3a0465ee37`; đây không phải runtime snapshot. **12/12** source hashes trong plan và **5/5** hashes bàn giao adapter khớp. **22/22** evaluation source/test hashes trước–sau khớp.

Đã chạy pytest toàn `tools/authorization-lab/tests/evaluation` với `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=tools/authorization-lab/src`, `.venv/bin/python`, cache tắt, basetemp tạm tự dọn. Dùng nội dung wrapper bàn giao nhưng đổi output thành `cmp07-adapter-independent-verification.json` để giữ nguyên evidence owner, thêm probes dưới cùng guards trước hash sau. **147 tests + 392 subtests PASS**, 1.21s; **4 QA probes PASS**, wrapper exit 0. Warning asyncio fixture scope unset là deprecation, không có test fail. Guards chặn socket connect/connect_ex/sendto/create_connection, DNS và subprocess.Popen/os.system/fork/posix_spawn; đây là guard Python trong process, không phải sandbox OS.

Evidence: [log](cmp07-adapter-independent-regression.log), [hashes trước/sau và probes](cmp07-adapter-independent-verification.json). Không sửa source/tests hoặc chạy lại wrapper theo cách ghi đè evidence owner.



## Independent QA addendum — CMP07 closure 2026-11-16 (T18 QA Evidence)

Giữ nguyên các kết luận và source evidence trước mục này. HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`, dirty/uncommitted. Đã audit → tái lập baseline 161 tests + 392 subtests → sửa 8 findings → retest/full tests → review source cuối. Không còn Critical/High in-scope có thể sửa được xác định mà còn mở.

| Requirement | Implementation / regression | Executed evidence | Independent verdict / giới hạn |
|---|---|---|---|
| CMP07-TRANSPORT-01: bounded GET/caps/redirect/proxy/retry/timeout/cleanup | bounded_http.py; test_bounded_http.py và test_cmp07_closure.py::test_independent_reconciliation | results/cmp07-independent-20261116/lab-closure.json; reconcile-*.json | PASS local loopback; không live target |
| CMP07-CANCEL-RECEIPT-01: cancellation/journal/no-replay | bounded_adapter.py, adapter_journal.py; checkpoint cancel, process kill pending HTTP, recovery lock/ID/fsync tests | evaluation-closure.json; crash-boundaries.json | PASS standalone; counts không phải server receipt, không durable per-response store, cross-layer recovery NOT VERIFIED |
| CMP07-WHOLEBODY-01: size/completeness/UTF8/JSON/403/baseline/policy/redaction | bounded_adapter.py; test_cmp07_closure.py và legacy adapter tests | evaluation-closure.json; failed repro logs trước sửa | PASS local policy-aware comparator/metadata; metadata chưa có consumer/schema2 receipt mới/live truth |
| Regression backend/SQLite và frontend | backend full / tmp SQLite concurrency; frontend unit/lint/build | backend-final.json, persistence-concurrency.json, frontend-{test,lint,build}.json | 170 backend + 49 frontend tests PASS; backend proof không được gán cho CLI journal |
| Browser/live research/DB preservation | mounted browser chỉ login heading; executable mock browser spec chưa chạy | browser.json; cmp07-closure-browser.spec.mjs | Browser NOT VERIFIED, live NOT_RUN, persistent DB proof UNKNOWN; tổng thể PARTIAL |

Evaluation cuối **201 tests + 392 subtests PASS**; toàn lab **367 tests + 531 subtests PASS**. Python compile 168 files, frontend lint/build và diff-check PASS. Không cộng tests focused trùng suite full.

Chi tiết requirement/test/evidence matrix, 8 fixes, reconciliation, trust model, giới hạn và file ownership: [cmp07-closure-independent-qa.md](cmp07-closure-independent-qa.md). Hash index: [cmp07-closure-sha256.txt](cmp07-closure-sha256.txt). Không tác động lab/Run #2/persistent DB/ZAP/BFLA; không commit/push/reset. Lead final independent review chưa được thực hiện trong lượt QA này.


## AUTOAUTH-QA-04 — independent verification, 2026-11-16

**PASS local regression/synthetic browser; overall PARTIAL.** QA rerun: 221 backend + 55 frontend tests, lint/build/diff exit 0; focused 51 nằm trong backend suite. Deterministic 3 identities/2 roles: 27 cases; probes 3 roles: 27, 5 roles: 65, mọi identity represented. Mounted browser temp app: explicit 3 selected cases, 8/8 responses, results/comparison stable case→run→artifact; stale revision blocks new queue; cancellation during pending request ends CANCELLED with 1/4 requests. Temp sentinel/snapshot/redaction PASS. Hashes exec 56/56, web 24/24; model old manifest 11/13 (2 files superseded by execution ticket), không claim model manifest PASS.

Responsive multi-viewport và persistent DB/Run #2 preservation proof **NOT VERIFIED**; manual/ZAP/write-BFLA **NOT_RUN**. Cancellation DTO uses NOT_EVALUATED outside six filters: taxonomy follow-up. No production edits, persistent access, writes/ZAP or commit/push. Exact evidence/commands/limits: [autoauth-qa-04.md](autoauth-qa-04.md), [execution](autoauth-qa-04/execution.json), [browser](autoauth-qa-04/browser-observations.json), [cancellation](autoauth-qa-04/cancellation.json). This addendum supersedes older browser NOT VERIFIED only for the synthetic workflow exercised here.


## AUTOAUTH-QA-06 — 2026-11-16, T18 QA Evidence

**PASS local/synthetic; tổng thể PARTIAL.** QA độc lập: 232 backend + 58 frontend tests PASS, focused 66 nằm trong full; lint/build/diff exit 0. DB tạm kiểm projection lịch sử bất biến, cancelled/cap/scope → NOT_RUN và observation thiếu evidence → INSUFFICIENT_EVIDENCE. Mounted browser temporary run 2 CANCELLED: 1/3 requests, result NOT_RUN/CANCELLED, sáu Results filters hoạt động (NOT_RUN 1 row, còn lại 0). Taxonomy blocker QA-04 đã đóng local. Responsive nhiều viewport **NOT VERIFIED**: actual 1280×800, resizeTo không đổi; không có mounted resize action. Persistent DB/Run #2 **NOT VERIFIED**, manual/ZAP/write-BFLA **NOT_RUN**. Không claim research acceptance toàn bộ R1–R8. Commands/exits/artifacts và blocker: [autoauth-qa-06.md](autoauth-qa-06.md), [execution](autoauth-qa-06/execution.json), [browser](autoauth-qa-06/browser-observations.json), [filters](autoauth-qa-06/filters.json), [responsive](autoauth-qa-06/responsive.json). Không production edits/persistent access/lab writes/ZAP/commit/push.
