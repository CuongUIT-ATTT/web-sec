# CONTRACT-02 — Matrix và finding reproduction

Ngày 2026-11-13; T18 OpenAPI Matrix. HEAD xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`.

## Kết quả: PASS trong phạm vi contract và tests

Chỉ sửa `backend/app/api/workflow_routes.py`, `backend/app/api/workflow_schemas.py`; thêm `backend/tests/test_web_demo_contracts.py` và báo cáo này. Không sửa runner/evaluator/frontend/CLI, không commit/push/reset, không khởi động lab hay application runtime riêng. Giữ nguyên artifacts cũ. Không thấy AGENTS.md trong repo, backend hay các thư mục cha đã kiểm tra.

## Contract cho frontend

### GET /api/projects/{project_id}/matrix?operation_id=N&resource_id=R

Giữ nguyên list và các trường `case_key`, `control_type`, `actor_identity_id`, `resource_id`, `policy_status`, `warnings`.

Thêm trên mỗi row:

| Trường | Kiểu JSON | Ý nghĩa |
|---|---|---|
| operation_id | integer | DB operation ID của preview |
| owner_identity_id | integer | Owner từ resource fixture |
| resolved_decision | string hoặc null | ALLOW/DENY/UNKNOWN từ rule được resolver chọn |
| policy_id | integer hoặc null | Rule ID thực được chọn |
| policy_version | integer hoặc null | Version thực của rule |

NO_MATCH và UNRESOLVED_CONFLICT có ba trường policy/decision null. Explicit UNKNOWN có status RESOLVED, decision UNKNOWN và ID/version thật. Resolver giữ nguyên precedence identity-resource > identity > role-resource > role; conflict chỉ xét specificity cao nhất; tie cùng decision chọn ID nhỏ nhất. Admin không bypass. Preview luôn có identity.unverified_precheck, không phải thất bại verify runtime.

`case_key` không đổi: `resource:R:actor:I`. Khi UI ghép nhiều operations phải dùng `(operation_id, case_key)`; evidence dùng `(run_id, case_key)`. Không đổi key để tránh phá compatibility.

### GET /api/projects/{project_id}/findings[?run_id=N]

Không truyền run_id: giữ project aggregate, bao gồm findings chưa có reproduction. Các trường cũ giữ nguyên; thêm `reproductions` là list:

```json
{"run_id": 1, "run_result_id": 1, "case_key": "resource:1:actor:2", "actor_identity_id": 2, "resource_id": 1}
```

Giá trị trên chỉ là fixture minh họa. Các trường lấy trực tiếp từ FindingReproduction join RunResult và Run; không parse fingerprint hay suy diễn provenance. `case_key` có thể null với dữ liệu lịch sử: UI hiển thị unavailable, không chế key.

Truyền run_id: chỉ findings có reproduction của run đó; reproduction list và reproduction_count cùng được lọc theo run. Run không tồn tại hoặc thuộc project khác trả 404. Không truyền run_id thì count là số reproduction hợp lệ trong project. Historical malformed link sang run của project khác bị loại cả khỏi list/count. Thứ tự findings giảm dần ID; reproduction tăng dần ID.

Chưa thêm evidence API hoặc owner validity/baseline fields chưa persist. Không trả raw response_metadata trong reproduction linkage. Không thay đổi endpoint results hay auth/CSRF guards.

## Verification

Command:

```text
.venv/bin/python -m pytest -q backend/tests/test_web_demo_contracts.py backend/tests/test_policy.py backend/tests/test_matrix_generator.py backend/tests/test_workflow_api.py backend/tests/test_update_api.py
```

Exit 0: **18 passed, 1 warning in 4.59s**. Cảnh báo Starlette TestClient/httpx deprecation; pytest-asyncio cũng phát startup deprecation về unset fixture loop scope. Không cài dependency hay sửa configuration vì các cảnh báo này.

9 test instances mới: no-match/owner/admin không bypass; explicit UNKNOWN/version; unresolved conflict; role/resource/identity specificity và deterministic tie; 4 tổ hợp foreign/missing operation/resource; run reproduction scope/project isolation/null historical key và metadata không bị expose. Tests mới dùng SQLite tạm và router FastAPI riêng, không app lifespan/worker, không target traffic. Chạy thêm suites resolver, matrix generator, workflow và update compatibility có sẵn.

`git diff --check`: exit 0. Source diff trong ownership: 40 insertions, 4 deletions; test/report mới chưa tracked. Lệnh kiểm kê tổng hợp có exit 1 do `rg --files backend -g AGENTS.md` không tìm thấy file; không phải lỗi tests/diff.

## Giới hạn/handoff

Frontend/browser/live demo/lab: NOT_RUN. Full backend suite: NOT_RUN trong ticket này; 18 tests liên quan PASS. QA cần xác minh độc lập UI tiêu thụ nullable fields, run-filter count và historical unavailable. Evidence owner baseline metadata thuộc ticket evaluator/Lead; chưa thể kết luận demo end-to-end PASS từ contract tests.
