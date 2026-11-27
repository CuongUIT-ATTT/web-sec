# AUDIT-03 — Web demo baseline QA

- Run ID: AUDIT-03-bdbba99-20261113T133240Z.
- HEAD: `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`.
- Repo: `/home/cuong/Dự án/Bảo mật web/Project`.
- Thực hiện ngày 2026-11-13, khoảng 20:32–20:35 giờ Việt Nam (UTC+07:00); timestamps UTC chính xác trong từng JSON.
- Phạm vi: audit production source read-only; không cài dependencies, không commit/push/reset, không chạy API lab hay khởi động app/lab, không đọc nội dung `.env` hoặc giá trị secrets. Tests dùng fixtures/temp DB; không reset DB runtime.
- Working tree ban đầu: untracked `T18-context-snapshot.zip`, `context-snapshot/`, `audit-final/`; giữ nguyên artifacts có trước. Không thấy AGENTS.md trong repo hoặc các thư mục cha đã kiểm tra.

## Kết quả thực thi

| Nhóm | Kết quả | Exit | Phạm vi |
|---|---|---|---|
| Backend unit/regression/API TestClient | PASS | 0 | 73 passed; loại riêng vertical slice tự dựng HTTP lab |
| Frontend Vitest/jsdom | PASS | 0 | 3 tests / 1 file; API mocked |
| Frontend lint | PASS | 0 | `tsc -b --noEmit`; không phải ESLint |
| Frontend build | PASS | 0 | TypeScript + Vite; output riêng trong thư mục audit |
| Live vertical slice | NOT_RUN | — | `backend/tests/test_vertical_slice_integration.py` tự mở localhost server; giữ giới hạn không khởi động runtime |
| Live runtime / browser E2E | NOT_RUN / BLOCKED | — | Không chạy app/lab; browser báo không có Chrome |
| CLI authorization-lab suite | NOT_RUN | — | Ngoài baseline web được giao |

Không có suite đã chạy bị FAIL. PASS chỉ áp dụng các lệnh và phạm vi trên, không xác nhận toàn bộ demo hoặc evaluator semantics đúng.

## Lệnh và logs

- `backend-tests`: cwd `/home/cuong/Dự án/Bảo mật web/Project`; argv `[".venv/bin/python", "-m", "pytest", "backend/tests", "-q", "--ignore=backend/tests/test_vertical_slice_integration.py", "-p", "no:cacheprovider", "--tb=short"]`; exit `0`; `2026-11-13T13:32:40.467543+00:00` → `2026-11-13T13:32:47.991030+00:00`; log `web-demo-baseline-logs/backend-tests.log`.
- `frontend-test`: cwd `/home/cuong/Dự án/Bảo mật web/Project/frontend`; argv `["npm", "run", "test"]`; exit `0`; `2026-11-13T13:32:41.580082+00:00` → `2026-11-13T13:32:44.729213+00:00`; log `web-demo-baseline-logs/frontend-test.log`.
- `frontend-lint`: cwd `/home/cuong/Dự án/Bảo mật web/Project/frontend`; argv `["npm", "run", "lint"]`; exit `0`; `2026-11-13T13:32:44.729775+00:00` → `2026-11-13T13:32:45.453700+00:00`; log `web-demo-baseline-logs/frontend-lint.log`.
- `frontend-build`: cwd `/home/cuong/Dự án/Bảo mật web/Project/frontend`; argv `["npm", "run", "build", "--", "--outDir", "/home/cuong/Dự án/Bảo mật web/Project/audit-final/web-demo-baseline-logs/frontend-dist"]`; exit `0`; `2026-11-13T13:32:45.453953+00:00` → `2026-11-13T13:32:46.881911+00:00`; log `web-demo-baseline-logs/frontend-build.log`.

Mỗi lệnh có giới hạn 55 giây; không timeout. Backend có cảnh báo Starlette/httpx và pytest-asyncio loop-scope. Build cảnh báo output ngoài root frontend; đây là output audit có chủ đích. Không sửa hoặc cài dependencies để xử lý cảnh báo.

## Inventory và readiness

Python 3.14.8; Node v26.12.1; npm 12.2.1. Dependencies đã cài, version thực tế nằm trong `python-dependencies.log` và `frontend-dependencies.log`. `npm ls --depth=0` exit 0. Không có Playwright trong dependencies trực tiếp; Vitest/jsdom không cung cấp browser proof.

`.env` tồn tại nhưng nội dung NOT_READ. Năm biến AUTHZ admin/session/encryption/network/ports đều không hiện diện trong môi trường shell của audit; điều này không chứng minh `.env` thiếu cấu hình. Runtime settings validation NOT_RUN. Không in values, không hash secret files. Schema cấu hình thật dùng `AUTHZ_ADMIN_PASSWORD`, `AUTHZ_SESSION_SECRET`, `AUTHZ_SECRET_ENCRYPTION_KEY`, `AUTHZ_ALLOWED_TARGET_NETWORKS`, `AUTHZ_ALLOWED_TARGET_PORTS`.

Lab runtime digest NOT_VERIFIED; compose disposable dùng tag `vampi-week1:local`, không phải immutable digest. Không Docker inspect hay HTTP probe trong đợt này. SHA-256 và mtime UTC của OpenAPI `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` và toàn bộ fixture files nằm trong `inventory.json`. Đây là fixtures repository, chưa được chứng minh là fixtures đang chạy của demo. OpenAPI inline trong tests không phải spec runtime.

Browser status đã kiểm tra qua browser được gắn cho cuộc hội thoại; trả về “no Chrome to run here (Google Chrome is not installed)”. Không dùng browser thay thế. Không có automation liên quan: kiểm kê trả về không có automation.

## Coverage và khoảng trống

Backend regression hiện có kiểm tra policy specificity/conflict, principal mismatch, response invalid/truncated, HTTP 200 denial, 403 body leakage, request accounting, cancellation, crash/restart, no replay, persistence, authentication/CSRF, redaction và scope guards. PASS không xóa các semantics gaps đã được evaluator audit ghi nhận.

Frontend 3 ca chỉ chứng minh login gating, fixed external read-only workflow và identity edit không điền lại token. Chưa có browser/UI proof cho resource/policy wizard, role XOR identity, matrix detail, queue duplicate guard, cancel, findings linkage, owner baseline validity, responsive/accessibility.

3-role/5-role, admin policy, authorized sharing, anonymous/invalid identity, false-positive HTTP 204 và owner-baseline lỗi cần acceptance cases có policy/fixture/case_id rõ ràng; không suy ra runtime PASS từ tổng 73 tests. Chưa chạy runtime owner PASS + cross-user confirmed BOLA.

## Prerequisites E2E sau triển khai

1. Khôi phục Chrome cho browser được gắn; xác minh browser hoạt động trước khi lập E2E evidence.
2. Trong giai đoạn được phép chạy runtime, xác minh config an toàn mà không log secrets; chọn app/DB dành riêng cho acceptance, target localhost/IP allowlist và ports rõ ràng. Không reset DB hiện hữu.
3. Ghi lab image digest, git HEAD/status tại lúc chạy, OpenAPI SHA-256, fixture owners, 3/5 roles, policy version, timestamps/timezone và run_id trước E2E.
4. Xác minh owner baseline hợp lệ, sharing/admin/negative policy và scope; chỉ GET vào API target lab. Setup/control-plane writes tách khỏi target requests. Không ZAP active/BFLA/disposable writes.
5. Chạy login/session/CSRF → project/target → identities/OpenAPI/resources/policies/mappings → matrix → bounded queue/poll/cancel → results/findings. Gắn case_id/run_id với owner validity/status, actual status, policy và evidence redacted. Có owner PASS và cross-user CONFIRMED theo ground truth.
6. Lưu screenshot và artifact hashes, kiểm tra accounting/no replay/persistence; lỗi hoặc chưa chạy giữ FAIL/BLOCKED/NOT_RUN. Bridge optional chưa cấu hình không được ngăn tuyến demo chính.

## Evidence integrity

`web-demo-baseline-logs/SHA256SUMS` bao gồm báo cáo này và mọi log/build artifact hiện có (trừ chính manifest hash). `execution-manifest.md`, `runtime-acceptance.md`, `evidence-gaps.md` nằm trong thư mục logs thuộc ownership AUDIT-03 để tránh ghi đè báo cáo audit chung của teammate.
