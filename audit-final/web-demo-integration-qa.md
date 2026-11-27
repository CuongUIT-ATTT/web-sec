# QA-WEB-04 — Kiểm tra tích hợp độc lập

Run ID: QA-WEB-04-bdbba99-20261113T1350Z. Repo `/home/cuong/Dự án/Bảo mật web/Project`; HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; thời gian 2026-11-13 khoảng 20:48–20:52 Việt Nam (UTC+07). Source chưa commit. Đọc kế hoạch, báo cáo UI và diff backend/frontend; không sửa production/App.test.tsx, cài dependencies, commit/push/reset, khởi động app/lab hay đọc secret values. Không thấy AGENTS.md trong repo; baseline đã kiểm tra các thư mục cha. Giữ nguyên snapshot ZIP/context và báo cáo của người khác.

## Verdict

**FAIL gate regression frontend; chưa nghiệm thu demo.** Có lỗi stale response xuyên project tái hiện bằng mock. Backend synthetic/API tests, TypeScript lint và build PASS. Live/E2E/R5 NOT_RUN; readiness cấu hình runtime chưa xác minh.

| Gate | Status | Evidence |
|---|---|---|
| Backend unit/regression/TestClient | PASS | 139 passed, exit 0; loại `test_vertical_slice_integration.py` vì tự mở localhost HTTP lab |
| Frontend cuối | FAIL | 9 passed, 1 failed / 10; exit 1; 3 tests cũ + 7 regression mới |
| Frontend lint | PASS | exit 0; thực chất TypeScript `tsc -b --noEmit` |
| Frontend build | PASS | exit 0; TypeScript + Vite; output riêng trong logs |
| Diff whitespace | PASS | `git diff --check`, exit 0 |
| Browser inventory | PARTIAL | status thành công, t1 about:blank; chưa kiểm navigation/render |
| Browser E2E + live owner PASS/cross-user CONFIRMED | NOT_RUN | không khởi động runtime/lab theo scope |
| R5 empirical comparison, 3/5-role runtime | NOT_RUN | không có run/case thực nghiệm mới |
| Runtime digest/config readiness | NOT_VERIFIED | không inspect/start lab, không đọc secrets |

## Ticket trả Lead: QA-WEB-04-F01 (P1)

File `frontend/src/App.tsx:182` (`viewRun`), liên quan parent setters ở dòng 31–33 và project transition dòng 61–64. `selectedRun` ref thuộc RunPanel cũ vẫn giữ run id khi component unmount. Promise cũ hoàn tất vẫn gọi `onResults`/`onFindings` là setters của App, làm dữ liệu project cũ hiện trong panel project mới. Generation guard của refreshProject không bảo vệ callback viewRun.

Reproduction synthetic: có hai project; mở kết quả run project 1, giữ pending results; chuyển project 2 và chờ dữ liệu setup của project 2; resolve results cũ với case `previous-project-case`; case cũ xuất hiện ở bảng project 2. Test cuối trong `frontend/src/WebDemo.test.tsx` thất bại đúng assertion không được có case cũ. Đây là sai provenance hiển thị trong UI quản trị; không chứng minh backend authorization bypass hay rò rỉ giữa user.

Acceptance đề nghị: invalidate callback khi unmount/project đổi; chỉ publish results/findings nếu project và selection còn hiệu lực. Giữ regression hiện tại; yêu cầu cả results và findings cùng được bảo vệ. QA không sửa production.

## Regression mới và phạm vi

`frontend/src/WebDemo.test.tsx` có 7 ca: create role XOR identity + resource-specific UNKNOWN; edit giữ role/resource rồi đổi độc quyền sang identity; matrix actual owner/operation/decision/policy/version; findings gọi với run id, missing evidence UNAVAILABLE và bỏ response của run khác; duplicate queue pending; duplicate cancel pending; stale results sau đổi project (FAIL).

Sáu ca đầu PASS. API hoàn toàn mocked trong jsdom; synthetic fixture 1 owner/role và response matrix giả lập chỉ kiểm UI plumbing, không phải 3-role/5-role hay ground truth BOLA. Chưa test render evidence hợp lệ đầy đủ, same-run overlapping refresh, stale matrix/project, polling exhaustion, bridge cancel duplicate, browser accessibility/responsive. Không suy runtime PASS từ mock.

Lượt đầu 4 lỗi do test chờ shell trước khi fixture refresh xong. Đã sửa helper chỉ trong file test để chờ identity option; lượt kế 9/9 PASS. Sau đó thêm ca cross-project độc lập: kết quả cuối 9 PASS/1 FAIL. Giữ toàn bộ logs, không che lỗi production bằng skip/xfail.

## Review contracts và giới hạn

Đã đọc diff App/api/styles và backend routes/schemas/evaluator/runner, snapshot `reviewed.diff`. Matrix gọi resolver thật và trả policy id/version/decision; policy payload dùng subjectKind XOR và giữ resource. API transport session/CSRF không bị đổi trong diff api.ts. Evidence API typed strict allowlist và run/case provenance; invalid/missing trả null, UI fallback UNAVAILABLE. Backend tests gồm canary/redaction, malformed/history, policy specificity/conflict/UNKNOWN, project isolation và evaluator baseline; PASS chỉ là synthetic/API evidence. UI comparison ghi NOT_RUN/NO_TIMING và không bịa benchmark.

UI hiện là anchors trên station cards; wizard/page containers, matrix filter/sort, comparison import/export chưa đủ kế hoạch. Batch queue/cancel pending guard PASS; bridge cancellation và matrix stale response chưa được regression xác nhận. Finding type/UI vẫn chưa trình bày reproduction run/case linkage chi tiết dù API có dữ liệu; cần acceptance thực tế với findings.

## Inventory và exact execution

Python 3.14.8, Node v26.12.1, npm 12.2.1; dependency hiện hữu đủ chạy test/lint/build, không cài. Runtime environment chỉ ghi presence booleans của tên cấu hình, không values; `.env` NOT_READ. Lab digest NOT_VERIFIED. SHA-256/mtime UTC OpenAPI `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` và fixtures trong `inventory.json`. Hash source cuối trong `source-hashes.json`; HEAD không đủ định danh vì working tree modified.

Exact argv, cwd, start/end UTC và exit từng lệnh ở JSON cùng tên log. Commands: `npm --prefix frontend test`; `.venv/bin/python -m pytest -q backend/tests --ignore=backend/tests/test_vertical_slice_integration.py -p no:cacheprovider --tb=short`; `npm --prefix frontend run lint`; `npm --prefix frontend run build -- --outDir /home/cuong/Dự án/Bảo mật web/Project/audit-final/web-demo-integration-qa-logs/frontend-dist`; `git diff --check`. Mỗi subprocess timeout 55s; không timeout. Full backend gồm live vertical slice NOT_RUN (139 synthetic vs 140 tổng báo cáo Lead). Backend warning pytest-asyncio/Starlette deprecation; build warning outDir ngoài frontend là chủ đích.

Browser status được kiểm tra mới: trả t1 about:blank thành công. Không tiếp tục dùng blocker thiếu Chrome cũ; status chưa chứng minh browser có thể render app. E2E bị giới hạn bởi scope không chạy runtime/lab, không quy cho Chrome. Kiểm kê automation: không có automation của bot.

## Artifacts

Output report: `/home/cuong/Dự án/Bảo mật web/Project/audit-final/web-demo-integration-qa.md`.
Logs/commands/inventory/hash: `/home/cuong/Dự án/Bảo mật web/Project/audit-final/web-demo-integration-qa-logs/`.
Test: `/home/cuong/Dự án/Bảo mật web/Project/frontend/src/WebDemo.test.tsx`.
`SHA256SUMS` bao phủ report, test và artifacts của ticket, loại chính manifest; đã đọc lại đối chiếu hashes. Không tuyên bố COMPLETE khi thiếu E2E/R5 và còn regression FAIL.
