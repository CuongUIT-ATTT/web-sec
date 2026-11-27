# QA-WEB-04-F01 — Kiểm chứng độc lập stale response

**PASS phạm vi regression frontend; chưa nghiệm thu demo.**

Run ID: QA-WEB-04-F01-20261113T1354Z. Thực hiện 2026-11-13 khoảng 20:53–20:55 Việt Nam (UTC+07). HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`, working tree chưa commit. Đối chiếu `web-demo-integration-qa.md`, báo cáo UI và source thực tế. Không sửa production hoặc App.test.tsx; không cài dependencies, runtime/lab, commit/push/reset hay đọc secrets. Snapshot ZIP/context giữ nguyên.

| Kiểm tra | Kết quả |
|---|---|
| Frontend regression toàn bộ | PASS: 15/15 tests, 2 files, exit 0 |
| TypeScript lint | PASS: exit 0 |
| TypeScript + Vite build | PASS: exit 0 |
| git diff --check | PASS: exit 0 |
| Backend | NOT_RUN trong lượt recheck frontend này |
| Live runtime, browser E2E, R5, 3/5-role thực nghiệm | NOT_RUN |

Giữ 7 regression QA cũ và 3 tests App.test.tsx. Bổ sung 5 trường hợp thực thi: pending findings sau chuyển project; lỗi results sau chuyển project; lỗi findings sau chuyển project; cùng run hai request chồng nhau với response cũ thành công; cùng run hai request chồng nhau với response cũ lỗi. Các ca cùng run xác nhận cả results và findings mới vẫn hiện, response/error cũ không ghi đè. Ca cũ cross-project results nay PASS, đóng lỗi QA-WEB-04-F01 trong phạm vi mock regression.

Review `frontend/src/App.tsx:182–190`: mỗi viewRun tăng generation; cleanup project/unmount tăng generation và xóa selectedRun; chỉ publish results/findings cùng generation và run, catch chỉ publish error còn hiệu lực. Tests điều khiển promises để phản hồi cũ hoàn tất sau chuyển project hoặc sau request mới. API hoàn toàn mock trong jsdom, không gọi lab hoặc chứng minh backend authorization/live demo.

Lượt đầu 11 PASS/4 FAIL do mock findings chặn lời gọi initial project refresh (không có run_id), không phải lỗi production mới. Đã giới hạn pending findings cho lời gọi có run_id, dùng resetAllMocks để xóa implementation queue giữa các ca. Giữ log đầu, không skip/xfail hoặc sửa source để đạt PASS. Lượt cuối 15 PASS.

Exact argv/cwd/start/end UTC/exit ở `web-demo-stale-response-recheck-logs/commands-final.json`; lượt đầu ở commands.json. Commands cuối: `npm --prefix frontend test`; `npm --prefix frontend run lint`; `npm --prefix frontend run build -- --outDir /home/cuong/Dự án/Bảo mật web/Project/audit-final/web-demo-stale-response-recheck-logs/frontend-dist-final`; `git diff --check`. Mỗi subprocess timeout 55 giây, không timeout. Build warning output ngoài frontend là chủ đích. Node v26.12.1, npm 12.2.1; dùng dependency đã có.

Source SHA-256 trước/sau ở source-before.json/source-final.json; xác nhận App.tsx, api.ts, styles.css, App.test.tsx, lockfile và OpenAPI không thay đổi trong recheck. Test mới là file duy nhất có thay đổi giữa hai inventory đó. Không có AGENTS.md được tìm thấy trong repo và shared folder của bot. Lab digest/runtime readiness không kiểm tra lại vì scope cấm runtime. Không tái sử dụng blocker Chrome cũ; browser không được thử trong lượt này. Kiểm kê automation: bot không có automation.

Artifacts: báo cáo này, logs và build output trong `/home/cuong/Dự án/Bảo mật web/Project/audit-final/web-demo-stale-response-recheck-logs/`; tests ở `/home/cuong/Dự án/Bảo mật web/Project/frontend/src/WebDemo.test.tsx`. SHA256SUMS bao phủ báo cáo, test và mọi artifact riêng của recheck (loại chính manifest); đã đọc lại xác minh. E2E/R5 cần bằng chứng độc lập trước nghiệm thu demo.
