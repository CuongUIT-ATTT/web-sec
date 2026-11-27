# EVAL-01 — Guard và evidence persistence

Ngày 2026-11-13; HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd.

## Phạm vi và kết quả

PASS: sửa đúng `backend/app/scanner/classification/evaluator.py`, `backend/app/workers/runner.py`; thêm `backend/tests/test_web_demo_evidence.py`. Không sửa workflow routes/schemas, frontend, CLI hoặc tests cũ. Những thay đổi routes/schemas và test contracts đang có thuộc ticket khác, được giữ nguyên. Không commit/push/reset, khởi động lab hay gửi request lab. Tests dùng SQLite tạm và stub transport cho các ca evidence.

- UNKNOWN → INSUFFICIENT_EVIDENCE (`policy.unknown_decision`), không PASS/CONFIRMED.
- Owner baseline trong cả legacy single và batch chỉ valid khi principal verification completed 2xx, không truncated/parse error; baseline completed 2xx không truncated/parse error; đúng resource external ID; mọi restricted pointer tồn tại và có evidence nonempty.
- Restricted evidence kiểm tra đệ quy: null, chuỗi rỗng/whitespace, dict/list rỗng hoặc chứa leaf null/rỗng không đủ. Số 0 và bool false là giá trị có evidence; equality phân biệt bool/number bằng JSON serialization. Object key order được bỏ qua, list order được giữ. Không normalization dynamic fields mới.
- Invalid owner → INVALID_TEST (khi policy đã resolve và actor observable); không suy ra denied PASS. Conflict/no-match và transport gates vẫn giữ thứ tự ưu tiên cũ.
- Actor completed 403 vẫn CONFIRMED nếu DENY + principal/resource/restricted owner evidence đầy đủ. Không dựa riêng vào HTTP 200.

## Contract metadata chính xác cho Lead

Áp dụng **chỉ result actor đã thực thi mới**, cả single và batch. `RunResult.response_metadata` là JSON object:

| Key | Type / ý nghĩa |
|---|---|
| body_length | int, chiều dài body actor |
| body_truncated | bool, actor |
| json_parse_error | bool, actor |
| evidence | object theo bảng dưới |

`response_metadata.evidence` có các key cố định:

| Key | Type |
|---|---|
| schema_version | int, luôn 1 |
| engine | string, luôn `web-evaluator-v1` |
| run_id | int, Run.id thực tế |
| case_key | string, đúng RunResult.case_key |
| resource_id | int, fixture Resource DB ID, không external ID |
| actor_identity_id | int, Identity DB ID |
| owner_identity_id | int, owner Identity DB ID từ immutable snapshot |
| owner_control_valid | bool |
| owner_http_status | int hoặc null |
| owner_execution_status | ExecutionStatus string |
| owner_body_truncated | bool |
| owner_json_parse_error | bool |
| owner_principal_matches | bool, từ verification response |
| actor_principal_matches | bool, từ verification response |
| owner_resource_matches | bool |
| actor_resource_matches | bool |
| owner_restricted_evidence_valid | bool, mọi configured restricted pointer nonempty |
| restricted_fields_match_owner | bool, toàn bộ restricted evidence nonempty và equality |
| policy_id | int hoặc null, selected rule thực tế |
| policy_version | int hoặc null |
| policy_decision | `ALLOW`, `DENY`, `UNKNOWN` hoặc null |
| policy_resolution | `RESOLVED`, `NO_MATCH`, `UNRESOLVED_CONFLICT` |

Các booleans comparison chỉ mô tả body quan sát, **không phải verdict**: có thể true với owner HTTP 500 nhưng owner_control_valid=false. UI phải đọc execution/conclusion/reason codes cùng validity, không dùng match=true để tự xác nhận. Policy UNKNOWN có thể resolution=RESOLVED, nhưng conclusion insufficient. Conflict không chọn một rule nên policy id/version/decision=null.

Case key single: `resource:{internal_resource_id}:actor:{internal_identity_id}`. Batch: `operation:{internal_operation_id}:resource:{internal_resource_id}:actor:{internal_identity_id}`. Không tạo case_id hay artifact ID giả. Persist qua RunResult sẵn có và claim fingerprint của batch; finding reproduction tiếp tục trỏ chính RunResult như trước.

Không persist response/raw body, restricted values, token/header, principal value, external resource ID, pointer names, URL/path, labels hoặc exception text. Không thêm fields ngoài allowlist từ snapshot. Lead có thể expose object này bằng schema allowlist; **không dump arbitrary metadata**. Existing API chưa được thay đổi trong ticket này.

## Verification

1. `.venv/bin/python -m pytest -q backend/tests/test_web_demo_evidence.py backend/tests/test_evaluator.py backend/tests/test_batch_runner_regressions.py backend/tests/test_batch_runner_idempotency.py` → exit 0, **51 passed** (4.48s). Log: `audit-final/web-demo-evidence-targeted.log`.
2. `.venv/bin/python -m pytest -q backend/tests` → exit 0, **119 passed**, 1 Starlette warning (12.67s). Log: `audit-final/web-demo-evidence-backend.log`. Full suite chạy trước khi thêm hai ca cross-user/sharing cuối; hai ca này nằm trong lượt targeted 51 PASS sau đó.
3. `git diff --check` → exit 0.

Các ca mới: UNKNOWN/ALLOW/DENY, nested equality, type mismatch, public-only/generic error/wrong resource, null/empty/missing restricted values, principal verification partial, owner HTTP403/500/timeout/parse/truncated/wrong principal/wrong resource, metadata provenance + canary redaction cho single/batch, cross-user DENY CONFIRMED, authorized sharing ALLOW PASS, owner ALLOW PASS, actor403 body leakage.

Trong lượt thử đầu, fixture test dùng transaction context không tương thích batch checkpoint commit; sau đó dùng shallow copy nên SQLAlchemy không persist nested policy mutation. Đã sửa **test fixture** bằng session thông thường + deepcopy. Một lượt full ban đầu có lỗi race claim của external-lab API (dispatcher đã claim trước test); lượt full sau PASS. Không sửa production ngoài ownership để che lỗi này.

## Limits

- Không có ownership-field pointer trong snapshot hiện có: xác minh principal owner bằng verification endpoint và resource bằng fixture external ID; không tuyên bố đã đối chiếu một owner field trong body resource.
- Baseline là GET cùng operation/path/token owner trong run hiện tại, không có artifact baseline độc lập hoặc raw baseline persisted. Metadata provenance tham chiếu run/case/resource fixture, không phải chứng cứ raw có thể replay sau này.
- Cancellation/request-limit results vẫn metadata={} do chưa quan sát response. Lịch sử không backfill; thiếu evidence nghĩa là unavailable, không phải false/invalid tự suy diễn.
- Chính sách evidence nonempty đệ quy bảo thủ: restricted object có một leaf optional null cũng bị coi invalid; nên cấu hình pointers đến restricted fields cụ thể.
- CLI parity, live lab, browser/E2E và frontend/API integration: NOT_RUN trong ticket này.
- Đã kiểm tra automation: bot không có automation cần dừng.
