# BOLA-A01–A04 — Analyze implementation

Ngày 2026-11-15, T18 BOLA Evaluator. HEAD xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Đã đọc `research-workflow-bola-audit.md` và `research-workflow-ui-matrix-implementation.md` trước sửa. Bảo toàn diff có trước, gồm Matrix UI, foundation và evaluator. Không sửa semantics evaluator, snapshot, Run #2 hoặc DB runtime. Không lab/network/queue/deploy/ZAP/BFLA/commit/push/xóa.

## Kết quả source

- `backend/app/workers/runner.py::_evidence_metadata`: tạo evidence v2 cho execution mới từ chính resource/identity/owner của immutable run snapshot. Actor/owner role nullable, ownership self/same-role-other/cross-role/unknown. Chỉ công bố role dạng ASCII identifier tối đa 32 ký tự; role ngoài dạng này hoặc vắng mặt được ghi unavailable, không lấy cấu hình hiện tại bù vào. Alias identity dùng surrogate ID nội bộ đã có trong contract, không external ID/principal.
- Mỗi configured restricted pointer có alias `protected-N` theo thứ tự trong snapshot, owner/actor presence, JSON type và equality bằng chính comparator hiện tại. Không ghi pointer/value/body. Các checks là diagnostics, không thay thế owner validity, principal, truncation hoặc quyết định evaluator. Engine vẫn web-evaluator-v1 vì semantics không đổi.
- `backend/app/api/workflow_schemas.py`: v2 kế thừa strict allowlist v1 nhưng yêu cầu đủ bốn trường mới; protected-field descriptor có schema riêng, type/alias giới hạn. v1 giữ nguyên output shape, không thêm null fields hoặc gán metadata mới cho lịch sử.
- `backend/app/api/workflow_routes.py::_result_metadata`: chọn validator theo version, vẫn bắt buộc khớp stored run_id/case_key; malformed hoặc thiếu v2 metadata trả unavailable. Không join policy/identity hiện tại. API findings dùng nguyên persisted reproductions đã có; không dựng provenance từ fingerprint.
- `frontend/src/api.ts`, `frontend/src/App.tsx`: Analyze giải thích sáu conclusion hiện có, hiển thị policy/version, actor/owner alias/role/ownership, baseline checks (principal/resource/protected evidence/truncation/parse), từng protected field, reason codes. HTTP chỉ là observation; không dùng status/length để nâng kết luận. Metadata thiếu hiển thị UNAVAILABLE. Artifact chưa có được ghi UNAVAILABLE, không tự tạo digest. Finding link tới row theo run_id/case_key; chỉ hiển thị reproduction thuộc run đang xem. Giữ guard chống stale response/project switch và UI Matrix/resource edit đã bàn giao.

Không tạo enum SUSPECTED/POLICY_DEPENDENT_ADMIN_ACCESS, không đổi persisted conclusion. Không đưa normalization/similarity CLI vào web. Single-run execution vẫn giữ legacy key, batch giữ canonical operation/resource/actor key; Analyze/drilldown dùng đúng persisted key, không chuyển đổi key lịch sử để khớp preview.

## Regression và fresh commands

Backend command từ root:

```sh
.venv/bin/python - <<'PY'
from unittest.mock import patch
import pytest
async def noop(*args, **kwargs): pass
with patch('backend.app.main.worker_loop', noop), patch('backend.app.main.external_lab_dispatcher_loop', noop), patch('socket.socket.connect', side_effect=AssertionError('network blocked')):
    raise SystemExit(pytest.main(['backend/tests/test_web_demo_evidence.py', 'backend/tests/test_web_demo_contracts.py', 'backend/tests/test_evaluator.py', 'backend/tests/test_finding_persistence.py', 'backend/tests/test_research_matrix_contract.py', 'backend/tests/test_batch_runner_regressions.py', '-q', '--tb=short']))
PY
```

**94 passed, 2 warnings, 7.97s; exit 0.** Worker/dispatcher no-op; socket connect bị chặn. Persistence fixtures dùng SQLite tmp_path; transport synthetic/stub. Không chạm DB runtime. Warnings: assert rewrite anyio, Starlette TestClient/httpx deprecation; pytest-asyncio có startup warning loop scope unset.

Coverage mới trong `backend/tests/test_web_demo_evidence.py`: v2 emission trong single/batch owner-failure matrix; typed alias/presence/equality; redaction canaries; strict DTO loại bỏ value extra, từ chối unsafe alias và mismatch run; cross-user DENY/ALLOW với owner role same/cross/missing từ snapshot. Existing tests tiếp tục cover UNKNOWN/conflict, DENY 403 body leak, principal mismatch, truncation, invalid owner, nested type equality, v1 exact allowlist, malformed/missing history, reproduction run/project isolation và idempotency.

Lượt đầu có **73 passed / 3 failed**: v1 bị thêm bốn null fields, và incomplete v2 không bị từ chối. Đã tách schema v1/v2 để giữ nguyên v1, bắt buộc metadata v2; không sửa assertions cũ cho xanh. Lượt sau **77 passed**, sau mở rộng role cases và runner/matrix suite đạt **94 passed** ở command cuối trên. Không còn failure trong suite này.

Frontend commands cuối, sau mọi chỉnh sửa:

```sh
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run lint
git diff --check
```

**28 tests passed, 3 files; exit 0**, bắt đầu 21:47:33 giờ Việt Nam, duration 6.70s. Build TypeScript/Vite **exit 0**, 17 modules. Lint (`tsc -b --noEmit`) **exit 0**. Diff check **exit 0**, không output.

Tests mới `frontend/src/Analyze.test.tsx`: đủ sáu conclusion explanations, missing legacy role/field metadata không backfill, evidence unavailable, v2 typed checks. `frontend/src/WebDemo.test.tsx`: finding reproduction link đúng run/case/row, loại foreign run; giữ tests stale response/project switch và Matrix/resource edit hiện có. Tests jsdom/API mocked, không phải Browser E2E.

## Dependency và giới hạn nghiệm thu

Source Analyze A01–A04 đã triển khai và regression nêu trên PASS. **Demo tổng thể PARTIAL; Browser E2E NOT VERIFIED.** Chưa phục vụ/deploy bundle để xác nhận người dùng đang thấy UI mới. Không dùng test mock làm thực nghiệm BOLA; gate 3+ roles, manual/ZAP/BFLA vẫn chưa được nghiệm thu bởi lượt này.

Compare cần dùng persisted run/case + policy/version và provenance từng method. Không dùng preview hiện tại để gán lại policy lịch sử; chưa chạy phải NOT_RUN. Chưa có artifact storage/digest thực tế thì unavailable. Nếu Compare cần canonical key cho single-run mới, cần ticket migration contract riêng; không tự đổi historical key.

QA/Lead cần Browser E2E độc lập trên môi trường được phép sau tích hợp Compare và phục vụ bundle mới: mở run, đối chiếu evidence v1/v2, click finding tới đúng row, đổi run/project không lộ evidence cũ. Không suy ra live Run #2 đã được kiểm tra hôm nay. Related automations đã kiểm tra: bot không có automation.
