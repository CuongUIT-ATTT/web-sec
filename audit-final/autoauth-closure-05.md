# AUTOAUTH-CLOSURE-05 — handoff cho QA

@T18 Lead: **PASS local regression; tổng thể PARTIAL.** HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd, uncommitted.

Đã đọc AUTOAUTH-QA-04. Authorization results API chuẩn hóa về sáu kết luận; không trả NOT_EVALUATED/BLOCKED_POLICY_CONFLICT. Row chưa có hoặc cancellation/cap/scope trước dispatch dùng NOT_RUN. Quan sát lỗi transport, body truncated/parse error hoặc evidence chưa đủ dùng INSUFFICIENT_EVIDENCE. execution_status/reason_codes giữ nguyên. Không xác nhận violation từ HTTP status đơn lẻ.

Cancellation helper chỉ ghi NOT_RUN khi snapshot.run_kind=AUTOAUTH_SELECTED; legacy tiếp tục NOT_EVALUATED. Evaluator mới nhận pre-dispatch cancellation/cap/scope là NOT_RUN; evaluator legacy không thay đổi. Public projection chỉ đọc: historical row NOT_EVALUATED vẫn tồn tại nguyên vẹn trong storage; không migration/backfill/sửa snapshot.

## Regression thực chạy

- Focused execution + legacy cap/cancel/evaluator: **66 PASS**, exit 0.
- Full backend: **232 PASS**, exit 0.
- Full frontend: **58 PASS / 6 files**, exit 0.
- Frontend lint/build + git diff --check: exit 0.
- Backend có cảnh báo Starlette/httpx deprecation; không failure.

Tests thêm: cancellation ở 0/1/4/5/6/24 checkpoints giữ durable results, cancelled rows NOT_RUN; DTO projection cho cancellation/cap/scope, timeout/network, partial body/parse error và cancellation có evidence. Assert row lịch sử, reason/status và snapshot không đổi sau đọc results. Evaluator pre-dispatch 3 statuses. Frontend filter NOT_RUN cancellation/cap và INSUFFICIENT_EVIDENCE partial body, giữ reason/status hiển thị.

Lượt frontend đầu 3 test mới fail vì exact text matcher không khớp reason nằm trong cell có nội dung khác; sửa assertion sang regex, rerun 58 PASS. Không sửa product UI vì lỗi test selector. Các số focused nằm trong full, không cộng vào total.

## Ownership / QA replay

6 files: backend/app/services/authorization_execution.py; backend/app/api/authorization_routes.py; backend/app/workers/runner.py; backend/app/scanner/classification/evaluator.py; backend/tests/test_authorization_execution.py; frontend/src/AuthorizationWorkflow.test.tsx.

Evidence và SHA-256 nguồn: /home/cuong/Dự án/Bảo mật web/Project/results/autoauth-closure-05/execution.json. Logs cùng thư mục. Commands/exits nằm trong execution.json. QA kiểm độc lập API cancelled kết luận NOT_RUN và filter Results; không cần truy cập persistent DB.

Không mở persistent SQLite/Run #2, không write lab/ZAP/commit/push. Browser chưa rerun ở ticket này; responsive/persistent proof vẫn NOT VERIFIED; manual/ZAP/write-BFLA NOT_RUN. Không automation của bot (list rỗng).
