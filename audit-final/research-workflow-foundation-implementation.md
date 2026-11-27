# Phase 2 foundation — REDACT-01, MATRIX-01/02

Ngày: 2026-11-15. HEAD kiểm tra: `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`.
Trạng thái: **PARTIAL**, foundation có diff và test thực thi; chưa nghiệm thu workflow web/runtime.

## Phạm vi thay đổi

Chỉ sửa các file được giao:

- `backend/app/api/workflow_routes.py`: `get_batch_matrix` trả cases từ chính `BatchPlan`; `get_matrix` dùng cùng presentation, chặn operation không selected GET/mapping không selected/resource không tương thích/owner ngoài tập identity. `_run_view` chỉ trả snapshot summary allowlist; `create_run` cũng đi qua `_run_view` thay vì trả ORM snapshot trực tiếp. Resource list/create/update trả alias và marker che ID.
- `backend/app/api/workflow_schemas.py`: bổ sung batch `cases` và trường matrix actor/owner alias, role, ownership, expected decision, method/path template. Resource response tách khỏi input; PATCH cho phép bỏ `external_id` để giữ giá trị hiện tại.
- `backend/app/scanner/matrix/generator.py`: thêm optional `operation_id` để tạo key batch; caller cũ không truyền vẫn giữ key cũ.
- `backend/app/services/batch_plan.py`: reject cấu hình project khác và selected mappings trùng. Không đổi công thức budget hay queue.
- Thêm `backend/app/services/demo_presentation.py`: `matrix_rows` dùng resolver policy hiện có; `public_snapshot` chỉ copy số lượng/count plan đã allowlist, không trả nested config hay dữ liệu tùy ý.
- Thêm `backend/tests/test_research_matrix_contract.py`: 6 tests isolated SQLite/read router, không app worker lifecycle/network.

Các diff đã có từ trước trong routes/schemas được giữ; thống kê git diff so với HEAD gồm cả diff cũ, không đại diện riêng lượt này. Không sửa frontend, runner/evaluator, model, migration, snapshot serializer hoặc tests cũ.

## Contract bàn giao frontend

`GET /api/projects/{id}/batch-matrix?target_id={id}` giữ các trường count/targets cũ, thêm `cases`:

```json
{
  "case_key": "operation:1:resource:1:actor:1",
  "operation_id": 1,
  "method": "GET",
  "path_template": "/items/{id}",
  "control_type": "CROSS_IDENTITY",
  "actor_identity_id": 1,
  "actor_alias": "identity-1",
  "actor_role": "admin",
  "resource_id": 1,
  "resource_alias": "resource-1",
  "owner_identity_id": 2,
  "owner_alias": "identity-2",
  "owner_role": "reader",
  "ownership_category": "CROSS_ROLE",
  "policy_status": "RESOLVED",
  "expected_decision": "DENY",
  "resolved_decision": "DENY",
  "policy_id": 1,
  "policy_version": 3,
  "warnings": ["identity.unverified_precheck"]
}
```

Đây là ví dụ giả lập sanitized từ contract test, không phải kết quả lab. Aliases được tạo từ surrogate DB ID; không dùng display name/principal/resource external ID. Ownership là OWNER/CROSS_USER (khác identity, cùng role)/CROSS_ROLE, không tự suy luận quyền admin. UNKNOWN/no match/conflict không thành ALLOW/DENY giả. Warning verification thể hiện preview chưa có precheck runtime.

Matrix đơn trả cùng rows của cặp operation/resource thuộc mapping đã chọn. Không render path bằng resource ID.

Run `snapshot` public mới chỉ có `presentation_version`, `run_kind`, `identity_count`, `concrete_target_count`, `request_plan` với integer counts allowlist. Không có target base URL, expected principal, external ID, ciphertext, secret hay body. Unknown nested keys của historical snapshot không đi ra public DTO. Serializer không mutate snapshot.

Resource response giữ `external_id` dưới dạng `[REDACTED]`, thêm `resource_alias`. Input create vẫn nhận external ID; PATCH omit/null external ID để giữ, nhập giá trị mới để thay thế. PATCH marker `[REDACTED]` trả 422 để tránh ghi marker đè fixture thật.

## Fresh validation

Lần cuối, command:

```sh
.venv/bin/python -m pytest backend/tests/test_research_matrix_contract.py backend/tests/test_batch_plan.py backend/tests/test_matrix_generator.py backend/tests/test_run_snapshot.py backend/tests/test_web_demo_evidence.py -q
```

**49 passed, 1 warning, 3.08s**, exit 0. Có thêm pytest-asyncio unset loop-scope warning lúc khởi động. Test evidence suite hiện có dùng fixtures/mocks; đây chỉ là regression code, không phải thực nghiệm BOLA.

Coverage mới: policy/version/count parity; single/batch row equality; unique keys trên nhiều operation; reorder ổn định; deselect mapping giữ key còn lại; owner/cross-user/cross-role; no match và conflict UNKNOWN; foreign target/operation/project rejection; duplicate mapping; unselected operation rejection; redaction canaries trên resource/run API; historical synthetic Run #2 snapshot không mutate; resource PATCH bỏ identifier không mất cấu hình.

Lần chạy mở rộng trước đó:

```sh
.venv/bin/python -m pytest backend/tests/test_research_matrix_contract.py backend/tests/test_batch_plan.py backend/tests/test_matrix_generator.py backend/tests/test_run_snapshot.py backend/tests/test_web_demo_contracts.py backend/tests/test_web_demo_evidence.py -q
```

**72 passed, 4 failed, 6.20s**, exit 1 (trước khi thêm test PATCH cuối). Bốn failures đều ở `test_web_demo_contracts.py`: `test_no_match_preserves_keys_owner_and_no_admin_bypass`, `test_explicit_unknown_is_resolved_and_versioned`, `test_conflicting_top_rules_have_no_selected_policy`, `test_role_resource_then_identity_specificity_and_deterministic_tie`. Fixture cũ thiếu selected mapping, nên contract mới trả 422 trước resolver. Không sửa tests cũ theo ownership. Cần owner test cập nhật fixture mapping và expected prefixed keys; không bỏ scope validation để làm xanh test.

`git diff --check`: exit 0. Không chạy full suite/lifecycle tests có thể queue worker. Không gọi lab, CLI, ZAP, BFLA hoặc DB runtime. Không commit/push/reset/xóa.

## Dependencies và giới hạn cần xử lý

1. **Frontend bắt buộc cập nhật trước acceptance**: `frontend/src/api.ts` thêm case/resource alias types; `frontend/src/App.tsx` hiển thị cases, không prefill `[REDACTED]` thành giá trị edit, omit external ID khi giữ nguyên. UI hiện tại gửi marker sẽ nhận 422; cấu hình gốc được bảo toàn. Tests cũ kiểm tra external ID plaintext phải đổi sang redacted response + DB assertion khi được phân công.
2. **Runner đơn còn legacy key** `resource:{id}:actor:{id}`. Preview mới nối đúng batch key; batch worker hiện dùng chính `operation:{id}:resource:{id}:actor:{id}`. Cần ticket runner riêng nếu tiếp tục hỗ trợ execute đơn với canonical key. Không sửa runner hoặc snapshot v1 ở lượt này, không rewrite lịch sử. Với legacy results phải hiển thị provenance/key gốc, không giả định đã nối canonical ID.
3. Snapshot public là count-only summary; chưa đủ historical per-case analysis từ immutable snapshot. Ticket Analyze cần DTO allowlist riêng lấy role/owner/policy từ snapshot lịch sử, không join current config rồi coi là lịch sử.
4. Không đổi evaluator semantics, cap, queue-time credential copy, idempotency, HTTP retries/redirects. Các cơ chế này được giữ code; không tái chứng minh toàn bộ bằng runtime ở lượt này.
5. Preview rows là actor cases; identity verification và owner baseline vẫn là counters, chưa có coverage/skip/provenance cho mọi logical attempt. Alias theo surrogate ID ổn định trong DB hiện tại, không cam kết ổn định qua export/import DB.
6. Chưa có browser E2E, runtime 3/5 roles hoặc test thực nghiệm mới. Test historical Run #2 là fixture synthetic; **Run #2 thật không mở DB/không queue/không sửa**. Mọi bằng chứng Run #2 lịch sử và snapshot serializer được giữ nguyên.
7. Path trả về là template OpenAPI đã cấu hình, không render identifier; không có cơ chế scrub literal nhạy cảm do người dùng tự nhúng vào OpenAPI path/role. Cần fixture provenance và kiểm duyệt spec lab khi demo.

Không có automation đang hoạt động cho bot tại thời điểm kiểm tra cuối. Nghiệm thu tổng thể **PARTIAL / NOT VERIFIED runtime**.


## FOUNDATION-REG-01 — rework 2026-11-15

HEAD xác minh lại: `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Giữ nguyên working tree có sẵn. Lượt này chỉ sửa `backend/tests/test_web_demo_contracts.py`, `backend/tests/test_research_matrix_contract.py` và báo cáo này; không sửa production, runner/frontend/evaluator hoặc tests ngoài ownership.

### Nguyên nhân và thay đổi

Đã tái hiện chính xác **73 passed, 4 failed** (exit 1, 5.59s) bằng command mở rộng bên dưới trước khi sửa. Fixture matrix không tạo `OperationResourceMapping`; route trả 422 trước policy resolver. Thêm mapping GET `selected=True` đúng operation/resource type/project và khai báo operation selected tường minh. Đổi duy nhất expected preview key sang `operation:1:resource:1:actor:{id}`. Giữ nguyên assertions owner/admin không bypass, NO_MATCH, explicit UNKNOWN/version, conflict không chọn rule, specificity và deterministic tie. Keys legacy của historical reproduction/evidence fixtures giữ nguyên, không rewrite lịch sử.

Bổ sung bốn negative cases: mapping unselected, mapping missing, operation unselected, method POST đều phải 422. `session.delete` chỉ xóa mapping synthetic trong SQLite tạm của test, không xóa dữ liệu persistent/runtime. Bổ sung resource PATCH replacement: public trả `[REDACTED]`, không rò canary, stored identifier đổi đúng; coverage omit identifier và reject marker giữ nguyên. Không nới scope hoặc policy production.

### Kết quả cuối và command tái lập

```sh
.venv/bin/python -m pytest backend/tests/test_research_matrix_contract.py backend/tests/test_batch_plan.py backend/tests/test_matrix_generator.py backend/tests/test_run_snapshot.py backend/tests/test_web_demo_contracts.py backend/tests/test_web_demo_evidence.py -q
```

**81 passed, 1 warning, 6.13s; exit 0.** Bốn lỗi gốc đã hết. Có Starlette/httpx deprecation và pytest-asyncio unset loop-scope startup warning.

Đã chạy cả resource API liên quan, không bỏ qua failure:

```sh
.venv/bin/python - <<'PYTEST'
from unittest.mock import patch
import pytest
async def disabled_worker(*args, **kwargs):
    return None
with patch('backend.app.main.worker_loop', disabled_worker), patch('backend.app.main.external_lab_dispatcher_loop', disabled_worker), patch('socket.socket.connect', side_effect=AssertionError('network disabled for resource regression')):
    raise SystemExit(pytest.main(['backend/tests/test_research_matrix_contract.py', 'backend/tests/test_batch_plan.py', 'backend/tests/test_matrix_generator.py', 'backend/tests/test_run_snapshot.py', 'backend/tests/test_web_demo_contracts.py', 'backend/tests/test_web_demo_evidence.py', 'backend/tests/test_workflow_api.py::test_workflow_configuration_survives_api_reload', 'backend/tests/test_update_api.py', '-q', '--tb=short']))
PYTEST
```

**84 passed, 1 failed, 2 warnings, 6.07s; exit 1.** Worker/dispatcher bị thay bằng no-op trong process test, socket connect bị chặn; không queue run, không target traffic. Tất cả DB là SQLite tmp_path. Thêm pytest assertion rewrite warning do imports trước pytest.main.

Failure chưa giải quyết: `backend/tests/test_workflow_api.py:47`, `test_workflow_configuration_survives_api_reload` kỳ vọng `external_id == "book-1"`, thực tế `[REDACTED]` đúng public contract mới. Không sửa file này vì ngoài ownership. Dependency cho Lead/owner test: đổi response assertion thành redacted alias và kiểm tra identifier lưu trữ trong DB tạm để vẫn chứng minh cấu hình không mất. `test_update_api.py` cả 3 tests PASS. Test batch queue trong workflow suite không chạy vì có enqueue, ngoài phạm vi được phép.

### Handoff và giới hạn

FOUNDATION-REG-01: bốn lỗi gốc **PASS**; gate toàn bộ resource contract vẫn **FAIL** vì một assertion legacy ngoài ownership. Không coi kết quả test SQLite/TestClient là bằng chứng thực nghiệm BOLA hoặc browser E2E. Run #2 thật và snapshot lịch sử không mở/không sửa. Không lab/network/runtime DB/queue/CLI/ZAP/BFLA/deploy/commit/push. Không thay dependency frontend hoặc runner đơn đã ghi phía trên. Không có automation của bot khi kiểm tra kết thúc.


## FOUNDATION-REG-02 — rework 2026-11-15

**Gate resource + foundation: PASS — 85 passed, 2 warnings in 6.31s; fresh exit 0.** Không còn failure trong bộ 85 tests đã báo 84 PASS / 1 FAIL. Workflow web tổng thể vẫn PARTIAL; kết quả này là regression SQLite/TestClient, không phải evidence thực nghiệm.

Lượt này chỉ sửa `backend/tests/test_workflow_api.py::test_workflow_configuration_survives_api_reload` và báo cáo này. HEAD vẫn `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; giữ mọi diff cũ. Không sửa production/tests queue/frontend/runner/evaluator.

Assertion public đổi sang `[REDACTED]` và alias theo resource surrogate ID; cả create/list không chứa identifier fixture. Giữ các assertions cũ khác. Test tạo app mới sau khi đóng client đầu, đăng nhập và đọc lại cấu hình từ cùng SQLite tmp_path; response sau reload phải bằng response trước reload. Session của app mới kiểm tra trực tiếp Resource: external_id gốc `book-1`, owner_identity_id, path_parameter `id` và resource_type_id đều còn đúng. Các giá trị này chỉ là fixture synthetic, không phải dữ liệu lab. Redaction được kiểm tra ở presentation đồng thời persistence được kiểm chứng độc lập sau reload.

Command thực chạy (cùng đủ bộ 85 tests, không skip failure):

```sh
.venv/bin/python - <<'PYTEST'
from unittest.mock import patch
import pytest
async def disabled_worker(*args, **kwargs):
    return None
with patch('backend.app.main.worker_loop', disabled_worker), patch('backend.app.main.external_lab_dispatcher_loop', disabled_worker), patch('socket.socket.connect', side_effect=AssertionError('network disabled for resource regression')):
    raise SystemExit(pytest.main(['backend/tests/test_research_matrix_contract.py', 'backend/tests/test_batch_plan.py', 'backend/tests/test_matrix_generator.py', 'backend/tests/test_run_snapshot.py', 'backend/tests/test_web_demo_contracts.py', 'backend/tests/test_web_demo_evidence.py', 'backend/tests/test_workflow_api.py::test_workflow_configuration_survives_api_reload', 'backend/tests/test_update_api.py', '-q', '--tb=short']))
PYTEST
```

Worker/dispatcher no-op; socket connect bị chặn. Không chạy test batch queue. Cảnh báo: pytest assert rewrite anyio và Starlette/httpx deprecation; thêm pytest-asyncio loop-scope warning lúc khởi động. Không có unresolved failure trong phạm vi bộ này. `git diff --check`: fresh exit 0, không output. Không có automation khi kiểm tra cuối.

Giới hạn/handoff: Lead có thể nghiệm thu gate foundation/resource để chuyển UI/Analyze/Compare. Chưa chạy Browser E2E, lab/network/runtime DB/queue/ZAP/BFLA/deploy; không commit/push/xóa hoặc rewrite Run #2/snapshot lịch sử. Các dependency frontend/runner đơn và giới hạn historical analysis phía trên vẫn cần owner xử lý; tests này không chứng minh runtime hay khai thác BOLA.
