# AUTOAUTH-EXEC-EVAL-02 — execution/evaluator handoff

2026-11-16. Gửi T18 Lead. HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; working tree dirty có sẵn được giữ nguyên. Không commit/push. **PASS local cho adapter/evaluator/API trong phạm vi kiểm; tổng thể T18 PARTIAL.**

## Thực thi đã triển khai

Adapter mới `backend/app/services/authorization_execution.py` tạo snapshot schema 3, `run_kind=AUTOAUTH_SELECTED`, từ reusable config và preview hiện tại. Không đổi queue legacy hay giả `policy_id`. Request chọn case phải có target, policy revision và danh sách stable case IDs không trùng. Reject toàn selection nếu stale revision, unknown case, case không executable hoặc tổng budget vượt cap. Không tự chọn bớt case.

Snapshot lưu configuration/rules/sharing, revision, expectations/matched rules, stable IDs, operation/resource/principal metadata và baseline; credential ciphertext được copy vào RunIdentitySecret tại queue time. Public endpoints không trả internal snapshot/credential/external resource IDs. Mọi identity cần cho actor hoặc baseline đều được xác minh lại bằng credential snapshot.

Worker mới `backend/app/workers/authorization_runner.py` chỉ GET. Baseline được deduplicate theo operation/resource/authorized identity. Chỉ baseline có policy ALLOW trong snapshot, principal đúng, HTTP 2xx, body hoàn chỉnh/parse được, resource identity đúng và protected fields observable mới hợp lệ. Authorized actor có thể làm baseline thay owner khi preview cho phép; không suy quyền admin từ tên path.

BFLA GET yêu cầu operator cấu hình result identity pointer/value **và** protected result pointers khác result identity. Kết luận confirmed cần result identity đúng, protected result tương đương authorized baseline và policy DENY. Không xác nhận từ status/path/admin/marker đơn lẻ. Đây là contract quan sát kết quả chức năng do operator cung cấp, không chứng minh mọi loại side effect kinh doanh.

Evaluator mới `evaluate_authorization_case` tái sử dụng comparator hiện hữu. Disclosure được kiểm trước denial envelope, kể cả HTTP 403. Denial envelope được cấu hình rõ có thể chứng minh denial với HTTP 200. Protected disclosure đúng identity nhưng khác baseline => SUSPECTED_VIOLATION; thiếu bằng chứng => INSUFFICIENT_EVIDENCE; principal/baseline invalid => INVALID_TEST. Unknown policy không được queue. Truncated/parse/transport failures không thể thành confirmed.

NonGET luôn NOT_RUN ở preview, reason `DISPOSABLE_WRITE_AUTHORIZATION_REQUIRED`; queue reject. Không gọi CLI từ web.

## Sửa lỗi và compatibility

- Hủy giữa claim và worker dispatch trước đây có thể giữ CANCEL_REQUESTED; execute_run nay terminalize cancellation trước dispatch. Regression checkpoint thực thi với 0 request.
- Cancellation accounting bỏ qua case đã có durable claim, giữ kết quả completed thay vì thử ghi lại CANCELLED và gây fingerprint conflict. Kiểm checkpoint sau verification/baseline/actor và sau request cuối bằng SQLite connection độc lập; không sleep tùy ý.
- HTTP client web nay `trust_env=False`; vẫn GET, no redirect, không thêm retry.
- Duplicate JSON keys, NaN/Infinity và malformed Unicode bị parse error, không dùng marker bị ghi đè làm disclosure evidence.
- Optional evidence absent không thay hash revision của model phiên bản trước. Regression so digest với serialization gốc.
- Guard snapshot từ chối nonGET/budget sai/cap sai trước network; durable dispatch checkpoint có sẵn không replay. Recovery startup hiện hữu vẫn đánh dấu INTERRUPTED; không thêm auto resume.
- Không ALTER schema hay sửa bảng legacy; case findings được lưu trực tiếp trong RunResult và BatchCaseClaim. `finding_id=autoauth-result:<result_id>` là ID case finding, **không phải** ID bảng Finding legacy. Legacy finding aggregation/reproduction API không được dùng để trình bày kết quả mới.

## Contract frontend

Giữ session admin và `X-CSRF-Token` hiện hữu.

1. Đọc/ghi `/api/projects/{P}/authorization/config`, đọc `/preview?target_id=T` như contract MODEL-MATRIX-01.
2. `Approval.evidence` optional:

```json
{"operation_id":2,"kind":"BFLA","approved":true,"evidence":{"result_pointer":"/report/id","result_value":"fixture-report","protected_pointers":["/report/entries"],"denial_pointer":"/error/code","denial_value":"FORBIDDEN"}}
```

BOLA có thể dùng evidence chỉ gồm denial_pointer/value; resource identity/protected pointers vẫn lấy từ ResourceType. Với BFLA thiếu evidence, preview reason `FUNCTION_EXECUTION_EVIDENCE_REQUIRED`. Preview `execution_contract=EXPLICIT_SELECTED_CASES_V3_GET_ONLY`; vẫn NOT_RUN trước execution.

3. `POST /api/projects/{P}/authorization/runs`:

```json
{"target_id":1,"policy_revision":"<preview.policy_revision>","case_ids":["<explicitly-selected-stable-case-id>"]}
```

Trả 201 `{id,status,policy_revision,case_ids,request_plan}`. HTTP 422 nếu selection không còn hợp lệ. Chỉ gọi sau explicit selection. Không gọi nút queue legacy cho config mới.

4. Poll `/api/projects/{P}/runs` và hủy `/api/runs/{R}/cancel` theo API hiện hữu. Public snapshot hiển thị `AUTOAUTH_SELECTED` và count-only request plan.
5. `GET /api/projects/{P}/authorization/runs/{R}/results` trả run status và các case với stable case_id, result_id, finding_id nullable, artifact_ref, revision/matched_rule_keys, kind, expected decision, actor/resource/baseline IDs, execution/conclusion/reasons/status và booleans evidence. Chưa có durable result trả NOT_RUN. Không trả raw response, token, expected principal hoặc external IDs.

## Verification và evidence

Evidence mới trong ignored `results/autoauth-exec-eval-02/`; các lượt trước giữ nguyên, bản chốt ở `acceptance/`. Recorder `verify.py` ghi exact commands, UTC start/end, exit codes, Python/dependency versions, HEAD và source SHA-256 trước/sau kiểm thử. `SHA256SUMS` ở root evidence index toàn bộ artifacts và source/report.

- Focused authorization execution/model: **51 PASS** (42 execution regressions mới + 9 model tests).
- Full backend: **221 PASS**.
- Compile backend và test mới: PASS. `git diff --check`: PASS.
- BOLA loopback: 15 executable cases + 6 baselines + 3 verifications = **24 planned / 24 client attempts / 24 completed responses / 24 server receipts**.
- BFLA loopback: 3 cases + 1 authorized baseline + 3 verifications = **7 / 7 / 7 / 7**.
- Cả hai chạy với valid identities, actor verification failure, baseline-role verification failure: **6 actual loopback executions**; no replay khi gọi lại terminal run. Snapshot vẫn chạy bằng credential/principal tại queue dù live config/token bị thay sau queue.
- Deterministic fixture preview vẫn 18 BOLA + 9 BFLA = 27 rows cho 3 identities/2 roles/6 resources. 3 BOLA UNKNOWN không queue; mọi identity vẫn hiện rõ trong preview. NonGET BFLA và GET thiếu evidence vẫn NOT_RUN.
- Cancellation 6 checkpoints: trước dispatch, sau 1/4/5/6/24 responses. Independent file-backed SQLite session requests cancellation. Không dispatch thêm sau observed cancellation; giữ case completed, terminal/idempotent, không duplicate.
- Negative tests: missing baseline, unknown, wrong resource, failed principal, denial 200, disclosure 403, superficial success, duplicate JSON keys, nonfinite JSON, Unicode parse failure, bounded/truncated/timeouts, stale/duplicate/missing/nonGET selections, prior durable checkpoint, CSRF/auth/project isolation/redaction.

Lệnh tái lập từ repo:

```sh
.venv/bin/python -m pytest backend/tests/test_authorization_execution.py backend/tests/test_authorization_model.py -q
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m compileall -q backend/app backend/tests/test_authorization_execution.py
git diff --check
```

Lượt `verified/` giữ nguyên FAIL: assertion redaction dùng substring `protected` vô tình match tên boolean metadata `protected_fields_match_baseline`. Đã thay fixture bằng giá trị bí mật synthetic riêng `fixture-private-result-742` và kiểm giá trị này không xuất hiện; không loại bỏ kiểm redaction. Lượt `acceptance/` chạy lại focused và full backend trên source hash ổn định.

## Giới hạn nghiệm thu

| Hạng mục | Trạng thái |
|---|---|
| Selected-case queue/snapshot, BOLA + configured GET BFLA evaluator/API | PASS local |
| Controlled isolated loopback execution/counters/token failure | PASS local |
| Cancellation/checkpoint/no terminal replay regressions | PASS local |
| NonGET disposable execution | NOT_RUN — cần authorization riêng |
| Browser E2E, five-screen workflow, comparison frontend | NOT VERIFIED — giao frontend tiếp |
| Manual/T18/ZAP và BFLA thực nghiệm nghiên cứu | NOT_RUN — fixture test không thay evidence nghiên cứu |
| Persistent DB/Run #2 preservation proof | NOT VERIFIED — không mở hoặc sửa persistent DB |
| Legacy aggregate Finding API cho revision-backed cases | Không tích hợp; dùng case findings API mới |
| Cross-process CLI/backend recovery/sidecar exactly-once | NOT VERIFIED; không mở rộng claim CMP07 |

Không sửa frontend, model bảng/migration, persistent DB, lab state, Run #2, ZAP hoặc thực thi write. Tests chỉ SQLite tạm và server numeric loopback riêng. Full backend PASS không thay thế browser/research acceptance.

## Files của ticket và review cuối

Mới: `backend/app/services/authorization_execution.py`, `backend/app/workers/authorization_runner.py`, `backend/tests/test_authorization_execution.py`, báo cáo này và ignored evidence. Chỉnh tiếp file model-team: `authorization_model.py`, `authorization_routes.py` (evidence contract + queue/results); đã thông báo trong room. Chỉnh `runner.py`, `evaluator.py`, `http_client.py`, `domain/contracts.py`, `services/demo_presentation.py`. Mọi diff khác đã có trước, không nhận là của ticket.

Review cuối: kiểm explicit approval/selection, GET-only dispatch, authorized baseline, immutable expectations/credential copy, cap, no retry/no redirect/proxy isolation, cancellation durable result, journal no replay, result allowlist và namespace traceability. Không xác định Critical/High chưa xử lý trong phạm vi review local; cần QA/reviewer độc lập của Lead. Không tuyên bố tổng thể research PASS.
