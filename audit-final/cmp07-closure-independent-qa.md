# CMP07 — independent QA/remediation closure, 2026-11-16

**Transport PASS local; whole-body PASS local; cancellation/journal PASS cho contract standalone đã kiểm. Nghiệm thu xuyên CLI–backend–Browser NOT VERIFIED; tổng thể T18 PARTIAL.** Không dùng kết quả synthetic làm ground truth CMP07 thực nghiệm. Người kiểm: T18 QA Evidence, tự chạy và review; chưa phải final review của Lead.

## Revision, phạm vi và môi trường

Repo tuyệt đối `/home/cuong/Dự án/Bảo mật web/Project`; HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`, dirty trước và sau, không commit/push/reset. Người dùng cho phép sửa source/tests non-destructive. Đọc `cmp07-transport.md`, `cmp07-adapter-independent-qa.md`, plan/review, implementation và acceptance docs. Không phát hiện AGENTS.md áp dụng trong đường dẫn workspace đã kiểm.

Python 3.14.8; pytest 9.2.0; pytest-asyncio 1.4.1.post1; FastAPI 0.162.0; SQLAlchemy 2.1.6; httpx 0.28.1; Node v26.12.1; npm 12.2.1. Timestamps evidence UTC ISO-8601; giờ địa phương UTC+07 (Asia/Ho_Chi_Minh). Inventory và dependency versions: `results/cmp07-independent-20261116/inventory.json`. Inventory HEAD/status thực hiện trước test; inventory dependency/fixture bằng file được hoàn thiện sau lần test đầu, không có runtime inventory.

OpenAPI SHA-256 `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b`. Fixture/handoff hashes có trong inventory. Lab image digest và current runtime fixture **UNKNOWN**, vì không truy cập lab. Fixture synthetic là `setup()`/`BOOK`/`IDENTITIES` trong `test_bounded_adapter.py`, không phải 13 cases CMP07 thật; không có live run_id. Case IDs QA bắt đầu `CMP07-QA-`; execution ID synthetic từ fixture, fixture hash c×64, policy v1/DENY hoặc ALLOW-sharing test. Không coi các giá trị này là attestation.

Evidence mới ở ignored directory `results/cmp07-independent-20261116/` (`git check-ignore` đã xác minh). Không ghi đè evidence người triển khai. Không sửa Run #2, historical findings, persistent DB, trạng thái lab; không chạy ZAP/BFLA/remote target. Listener mới dùng numeric 127.0.0.1:ephemeral; SQLite mới dùng pytest tmp_path. Không có token/header/response thật trong evidence. Canaries trong failed-test diagnostics đều synthetic.

## Kết quả chạy độc lập

| Lớp | Kết quả thực chạy | Evidence |
|---|---|---|
| Baseline implementer suite tái lập trước sửa | 161 tests + 392 subtests PASS | baseline.json/.log |
| Evaluation cuối | 201 tests + 392 subtests PASS | evaluation-closure.json/.log |
| Toàn bộ authorization-lab cuối | 367 tests + 531 subtests PASS | lab-closure.json/.log |
| Backend full sau sửa fixture và concurrency tests | 170 tests PASS | backend-final.json/.log |
| Persistence/idempotency/concurrency focused | 11 tests PASS | persistence-concurrency.json/.log |
| Frontend unit | 49 tests / 4 files PASS | frontend-test.json/.log |
| Frontend lint, production build | exit 0 / exit 0 | frontend-lint.json, frontend-build.json |
| Python compile (không sinh bytecode), diff check | 168 files PASS, diff-check PASS | static-acceptance.json/.log |
| Browser | NOT VERIFIED cho transport/cancellation; chỉ đọc login heading | browser.json; executable spec cmp07-closure-browser.spec.mjs |
| Live CMP07/manual–T18–ZAP/BFLA | NOT_RUN | không có evidence thực nghiệm mới |

Các suite focused/evaluation là tập con của full lab; không cộng số tests trùng. Backend test có tên browser reload dùng TestClient, **không phải browser E2E**. Không có cấu hình Python lint/type checker riêng được tìm thấy; compilation không thay type checking. Warnings pytest asyncio scope và Starlette/httpx còn tồn tại, không có failing assertion do warnings.

Mỗi JSON execution record ghi exact command, start/end, process exit code, verdict, log/hash; các record cuối pin revision và source/test hashes. `run.py` đặt PYTHONDONTWRITEBYTECODE=1, PYTHONPATH=lab/src:repo; cache pytest tắt. Các run đầu chưa có per-file source snapshot, giữ log tái lập và không giả tạo snapshot trước sửa. Hai lần wrapper bổ sung hash gặp NameError sau khi test đã chạy; giữ `.log` của hai lần đó nhưng **không dùng làm acceptance**; sửa wrapper và chạy lại bằng ID mới `*-acceptance-final`, rồi `*-closure`. JSON exit codes phản ánh subprocess, không lấy exit 0 của wrapper cũ làm PASS.

## Findings và remediation (đã sắp severity; 8 findings, không còn Critical/High in-scope mở)

| ID | Severity | Repro/root cause | Fix nhỏ nhất và regression | Trạng thái |
|---|---|---|---|---|
| Q01 | High | journal.next cố định theo symlink, có thể truncate file khác | mkstemp O_EXCL/0600 + cleanup; test_journal_temp_symlink_cannot_overwrite | FIXED; defects-before FAIL → full PASS |
| Q02 | High | recovery song song đổi execution đang sống thành CRASH_RECOVERED | flock nonblocking trên lock file riêng sống qua rename, O_NOFOLLOW; test_recovery_rejects_live_execution | FIXED; journal-before FAIL → full PASS |
| Q03 | High | recover bằng execution ID khác có thể relabel journal | kiểm correlation trước mutation; wrong-execution test dùng journal terminal để tách khỏi live lock | FIXED; journal-before FAIL → full PASS |
| Q04 | High | cancel trong actor cuối bị nuốt như lỗi body, terminal vẫn COMPLETED | giữ stop ngay lúc quan sát cancel/read/close; giữ observation hoàn tất ở completion race | FIXED; final-cancel-before FAIL → full PASS |
| Q05 | High | actor 403 chứa disclosure bị bỏ qua trước đọc body | chỉ cho actor 403 đi qua bounded capture/comparator; identity/baseline vẫn cần 200 hợp lệ | FIXED; defects-before FAIL → full PASS |
| Q06 | Medium | chưa có whole-body observation metadata | thêm complete/byte count/parse/shape/equality/confidence redacted vào result, không đổi envelope schema2 | FIXED; defects-before FAIL → full PASS |
| Q07 | Medium | JSON 1e999 được parse thành inf nhưng vẫn coi hợp lệ | parse_float hữu hạn; overflow regression | FIXED; json-overflow-before FAIL → full PASS |
| Q08 | Medium | vertical-slice fixture thiếu selected operation-resource mapping của contract hiện tại | thêm explicit mapping + negative 422 trước mapping; không giảm assertion | FIXED; backend-full 1 FAIL → backend-final 170 PASS |

Fail evidence giữ nguyên: `defects-before`, `journal-before`, `final-cancel-before`, `json-overflow-before`, `backend-full`. Một lần focused `journal-after` fail vì test wrong-ID còn dùng live journal; sửa fixture terminal để kiểm đúng hai guard độc lập, không đổi kỳ vọng sai-ID bị từ chối.

## Transport và reconciliation độc lập

`bounded_http.py` không đổi: chỉ numeric-loopback HTTP, exact origin/path, GET qua một socket/dispatch, reserve cap trước await, không proxy env, không DNS/retry/redirect; fail-closed chunked/compressed/oversize. Existing integration tái chạy xác minh 200/204/401/403/500 và 301/302/303/307/308 không follow, timeout header/body, premature disconnect và socket cleanup. Negative scope/retry/proxy options chặn trước connection. Proxy environment trỏ TEST-NET nhưng direct stream không đọc proxy variables, không gửi traffic TEST-NET.

`test_independent_reconciliation` dùng handler counter riêng và Tracking wrapper quan sát client headers/EOF; evidence từng mode `reconcile-*.json`. Planned = 4; terminal sidecar **1/execution, không phải 1/request**.

| Case | Planned | Adapter | Transport | Headers | Full body | Scope | Errors | Server received | Server written | Journal | Terminal receipts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CMP07-QA-cap | 4 | 2 | 2 | 2 | 2 | 0 | 0 | 2 | 2 | 2 | 1 |
| CMP07-QA-connection | 4 | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0 | 4 | 1 |
| CMP07-QA-disconnect | 4 | 4 | 4 | 0 | 0 | 0 | 4 | 4 | 0 | 4 | 1 |
| CMP07-QA-normal | 4 | 4 | 4 | 4 | 4 | 0 | 0 | 4 | 4 | 4 | 1 |
| CMP07-QA-redirect | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 4 | 4 | 4 | 1 |
| CMP07-QA-scope | 4 | 4 | 2 | 2 | 2 | 2 | 0 | 2 | 2 | 4 | 1 |
| CMP07-QA-timeout | 4 | 4 | 4 | 0 | 0 | 0 | 4 | 4 | 0 | 4 | 1 |

`adapter_attempts = scope_blocked + transport_errors + client_headers`; client EOF-complete body là số khác client headers hoặc server đã write response. Connection failure chứng minh reservation/attempt 4 nhưng server receipt 0. Scope row cố tình cấu hình transport chặt hơn approval, không phát request ngoài allowlist. CAP_EXHAUSTED được ghi trong result.stop; sidecar COMPLETED nghĩa executor kết thúc, không có nghĩa mọi planned case đã chạy. Mọi reservation ≤ cap. Không dùng wrapper invocation làm server receipt proof.

Cancellation pending-header từng request 1/2/3/4: server count = transport count = journal attempts = checkpoint index; responses server đã write = index−1; unissued sequence slots = 4−index. Không đồng nhất unissued sequence slot với actor case count. Tests `test_cancel_each_http_phase_reconciles` dùng Event, không sleep, repeated cancel terminal idempotent; `test_real_socket_cancel` kiểm pending body và peer EOF. Predicate predispatch có durable CANCELLED [0,0,0]; external get/read/close cancellation có receipt. Task bị cancel trước khi coroutine được schedule không tạo execution reservation; audit của worker chưa bắt đầu thuộc orchestrator, không suy đã có sidecar.

## Journal/crash và trust model

- Reserve O_EXCL, mode 0600, fsync file + directory. ATTEMPTING được durable trước gọi transport; nó chứng minh reservation phía client **trước** server acceptance, không chứng minh delivery.
- Atomic unique-temp → replace → fsync directory. Sau lời gọi write trả thành công có durable checkpoint trong phạm vi OS/fsync contract; không có remote acknowledgement service.
- execution_id do caller cung cấp, pin vào Approval; kiểm equality, wrong-ID recovery bị từ chối. Không phải chữ ký hay secret; caller phải sở hữu parent directory, không xóa/đổi journal path/lock file để né guard.
- Live execution giữ flock; process chết giải phóng lock, recovery chỉ terminalize uncertain state, không gọi HTTP. Torn/empty journal giữ CRASH_RECOVERED; invalid counts/wrong ID fail closed. Có fsync-failure injection và interruption sau atomic replace; chưa kiểm power loss/storage hardware/fsync treo.
- Duplicate reservation cùng path bị từ chối trước dispatch; repeated recovery terminal giữ bytes/counts/digest. Missing journal hoặc operator đổi path **không được bảo vệ**. Không có queue receipt bất đồng bộ hay dedup service; delayed/duplicate delivery receipts không phải khả năng của module này.
- Kill child thật trong HTTP pending: dedicated server đã thấy đúng 1 request, peer đóng sau kill; recovery giữ [1,0,0], CRASH_RECOVERED; rerun không dispatch. `test_process_crash_no_replay` cũ cũng kill sau durable checkpoint. Các label RESPONSE_OBSERVED/RESULT_PERSISTED trong test interruption là **fault-model synthetic states**, không phải production checkpoints có sẵn.
- Existing backend crash-after-dispatch/persistence/idempotency tests và hai concurrency tests file-backed SQLite chạy riêng. Claim/cancel/completion atomic được kiểm bằng independent sessions; no duplicate RunResult/Finding/FindingReproduction ở các scenarios đã chạy. Không gán bằng chứng SQLite này cho journal CLI: adapter không import backend, journal không ghi các bảng đó.
- Sidecar terminal lưu counts và result digest (nếu return thành công), **không lưu toàn bộ per-response/result payload**, không restore result envelope và không attested ground truth. External cancellation giữ counters nhưng không trả envelope. Request không đi qua adapter/journal (legacy/backend/manual/ZAP/transport dùng trực tiếp) không có sidecar này. Chỉ các loopback cases kiểm soát mới đối chiếu được với server logs.
- **Exactly-once delivery, exact server receipt trong crash window, cryptographic authenticity, durable per-case observation store và xuyên CLI–backend recovery NOT VERIFIED.** Đây là ranh giới kiến trúc/contract, không được tự nối web→CLI để đóng gate.

## Whole-body acceptance matrix

Implementation: `bounded_adapter.py` request(), _finite_float(), _shape(), actor comparator; transport framing/body limit: `bounded_http.py`. Regression: `test_cmp07_closure.py`, `test_bounded_adapter.py`, `test_bounded_http.py`; evidence final evaluation/full logs.

| Requirement | Kiểm thực chạy / điều kiện quyết định | Verdict local |
|---|---|---|
| Maximum bytes | adapter sentinel limit+1, transport declared cap; oversize fail trước body; không decompress/chunked | PASS |
| Complete vs incomplete | complete chỉ sau EOF framing; limit/premature EOF/timeout giữ false; không so partial | PASS |
| UTF-8 byte count | đo len(bytes), có actual UTF-8 tiếng Việt, không đếm ký tự | PASS |
| JSON success/failure | strict UTF-8, duplicate keys/invalid/NaN/overflow fail; non-object/error object không đủ evidence | PASS |
| Non-JSON error | bounded capture, complete=true nếu đủ bytes, json_valid=false; không confirm | PASS |
| Sensitive extraction/redaction | explicit frozen paths; exact typed present scalar, null/missing/empty fail; output không raw field/value/body/header | PASS |
| 403 disclosure | actor 403 vẫn cần identity + owner baseline + resource/owner + protected exact match + DENY | PASS |
| Baseline owner/object | verified identities và exact expected owner/object; wrong owner/resource không CONFIRMED | PASS |
| Legitimate sharing | policy ALLOW không CONFIRMED dù body giống owner | PASS |
| Ambiguous/insufficient | HTTP 200/204, byte length, shape/equality đơn lẻ không nâng conclusion; error/missing/null giữ INCONCLUSIVE | PASS |
| Whole-body normalization | json-typed-v1-no-fields-ignored; sort object keys, giữ array order/types; không bỏ timestamps; equality boolean, không similarity threshold | PASS |
| Sufficiency/confidence | POLICY_AND_DISCLOSURE chỉ khi explicit comparator + DENY; metadata còn lại INSUFFICIENT; không số confidence bịa | PASS |
| Provenance/schema compatibility | additive result evidence trong outer result digest; case/fixture/policy ở canonical manifest, execution/mapping/principal binding giữ nguyên; schema2 envelope validation cũ PASS | PASS |
| Metadata ingestion/attestation live | metadata chưa thành schema2 observation receipt mới; không consumer acceptance/attestation live | NOT VERIFIED |

Baseline raw bodies chỉ tồn tại trong memory để so sánh. Shape chỉ tổng loại JSON nodes; không field names/resource identifier. Canonical body hash chỉ dùng nội bộ cho equality, không phát ra evidence (tránh dò ngược protected values). Dynamic fields làm wholebody_equal=false nhưng **không phủ định** protected disclosure độc lập, cũng không tự xác nhận vi phạm.

## Final independent diff review và giới hạn

Review lại toàn bộ source sở hữu (gồm untracked, không chỉ git diff), transport unchanged và diff test backend. Không thêm method/URL/discovery/login/retry; không bỏ guard, không mở remote traffic, không sửa persistent data. Core fix chỉ bounded_adapter.py/adapter_journal.py; bounded_http.py không đổi. Backward compatibility envelope/schema2 giữ nguyên, batch backend full tests PASS. Historical handoff docs/logs không bị sửa. Diff review tự thực hiện sau remediation; Lead review độc lập cuối vẫn chờ bàn giao, không tự nhận Lead đã tham gia.

Các giới hạn còn lại có mức Medium/contract gap: sidecar không là durable result store/consumer authenticated receipt; atomic DB lifecycle và CLI không cùng một transaction; browser login gate và lỗi tài nguyên ERR_SOCKS_CONNECTION_FAILED chưa kiểm execution summary. Không chạy browser login, không thay service/persistent DB để vượt gate. Giữ executable isolated/mock UI spec, **NOT RUN**, không dùng unit PASS thay browser PASS.

## Matrix chốt

| Ticket/gate | Independent verdict | Giới hạn bắt buộc giữ |
|---|---|---|
| CMP07-TRANSPORT-01 | PASS — local dedicated-loopback acceptance | Numeric-loopback HTTP; unsupported framing fail closed; không live principals/approval |
| CMP07-CANCEL-RECEIPT-01 | PASS — standalone counters/journal/no-replay contract | Không exactly-once/server receipt/durable result payload; integrated backend/browser gate NOT VERIFIED |
| CMP07-WHOLEBODY-01 | PASS — bounded policy-aware comparator/metadata local | Không live truth, không metadata consumer/contract expansion |
| Extended cross-layer recovery/per-case durable result restoration | NOT VERIFIED | Chưa có isolated orchestration contract nối hai tầng; không thuộc journal hiện tại |
| Browser transport summary/cancellation E2E | NOT VERIFIED | Login gate; CLI transport không có UI bridge; spec chưa chạy |
| CMP07 live manual–T18–ZAP / BFLA | NOT_RUN | Không có scope/principals/truth/budget hiện tại đã kiểm; không chạy lab |
| Persistent DB preservation proof | UNKNOWN | Chỉ SQLite tmp fixture được kiểm; không truy cập DB persistent |
| Overall T18 research demo | PARTIAL | Còn thực nghiệm, DB preservation proof và Browser E2E riêng |

## File bàn giao và tái lập

Source thay đổi trong lượt: `tools/authorization-lab/src/authz_lab/evaluation/bounded_adapter.py`, `adapter_journal.py`. Tests mới: `tools/authorization-lab/tests/evaluation/test_cmp07_closure.py`, `backend/tests/test_cmp07_qa_concurrency.py`. Fixture compatibility sửa: `backend/tests/test_vertical_slice_integration.py` (test trước đó clean, không đụng owner active). Docs mới report này, browser spec, closure hashes; append QA addenda vào task-board.md, requirements-traceability.md, final-verdict.md và các docs QA runtime/evidence/manifest nếu có. Source/tests vẫn **uncommitted**, giữ mọi diff khác sẵn có.

Lệnh tái lập từ repo (không ghi đè evidence bàn giao):

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/authorization-lab/src:. .venv/bin/python -m pytest -q -p no:cacheprovider tools/authorization-lab/tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider backend/tests
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
sha256sum -c audit-final/cmp07-closure-sha256.txt
```

Evidence index/hashes: `results/cmp07-independent-20261116/evidence-index.json`, `audit-final/cmp07-closure-sha256.txt`; final source snapshots giữ trong evidence directory. Không có automation của bot cần pause (đã kiểm).
