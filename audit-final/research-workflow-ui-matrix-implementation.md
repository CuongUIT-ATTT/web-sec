# UI-MATRIX-03 — bàn giao frontend

Ngày 2026-11-15; requestId 796cf21d-9b50-4d5b-a02b-e5172c0b37c3.
HEAD đã xác minh bdbba9933ca057cb2247c3a1de9b3ee239c452bd. Working tree có diff từ trước; không reset/commit/push. Chỉ cập nhật frontend và báo cáo này trong lượt triển khai UI.

## Thay đổi

- frontend/src/App.tsx: CaseMatrix dùng chung cho ma trận đơn ở trạm 05 và batch preview tại trạm chạy. Hiện canonical case_key, method/path template, alias/role actor và owner, resource alias, ownership category, expected decision, policy/version/resolution và warnings. Lọc theo tài khoản và ALLOW/DENY/UNKNOWN, hiển thị số case sau lọc; ghi rõ NOT_RUN cho preview. Không suy diễn quyền admin từ role.
- IdentityPanel thêm identity-N để đối chiếu alias backend với tên tài khoản cấu hình.
- ResourcePanel thêm danh sách resource alias → tài khoản owner/role; các lựa chọn resource dùng alias thay external_id. Khi sửa resource, ID luôn trống; PATCH bỏ external_id nếu không nhập thay thế, tạo mới vẫn yêu cầu ID. Không nạp [REDACTED] vào ô chỉnh sửa.
- frontend/src/api.ts: bổ sung fields DTO ma trận, batch cases, resource_alias và PATCH cho phép bỏ identifier. Fields trình bày là optional để fallback cho dữ liệu/mock cũ; fallback không tự tạo quyết định ALLOW/DENY.
- frontend/src/styles.css: bảng cuộn ngang, cell wrap và caption cho case matrix.
- frontend/src/WebDemo.test.tsx: cập nhật assertion trình bày; thêm regression giữ/thay resource ID, matrix 3/5 tài khoản và filter, nối batch cases/warnings mà không queue run.

## Kiểm chứng mới

Tại root repo:

- `npm --prefix frontend test`: exit 0; 2 files, **19 passed**, 0 failed (21:43 giờ Việt Nam).
- `npm --prefix frontend run build`: exit 0; TypeScript + Vite, 17 modules; bản cuối mã production build thành công.
- `npm --prefix frontend run lint`: exit 0; script hiện có chạy TypeScript `tsc -b --noEmit`, không phải ESLint.
- `git diff --check`: exit 0.

Hai lượt test trước có lỗi assertion text của layout cũ; đã cập nhật kiểm tra nội dung region/cell, giữ xác nhận decision/resolution/policy/version. Kết quả cuối không bỏ test.

## Handoff / giới hạn

**Source UI PASS; Browser E2E NOT VERIFIED.** Tests là React/jsdom với mock API, không phải thực nghiệm authorization. Chưa deploy hay kiểm tra production web; không thể dùng kết quả này tuyên bố user đã thấy giao diện mới. Không chạy lab, queue, DB runtime, CLI, ZAP/BFLA hoặc sửa Run #2.

Lead cần nối Analyze bằng contract lịch sử đã redacted: cùng canonical case_key + run_id, baseline owner, policy/version tại thời điểm chạy, protected-field evidence và reason codes. Không dùng preview policy hiện tại để gán lại quyền cho run lịch sử. Compare cần contract từng case cho manual/T18/ZAP, provenance/artifact và explicit NOT_RUN; không có dữ liệu đủ thì không tính TP/FP/FN. Không thay evaluator/runner trong assignment UI.

Bộ dữ liệu synthetic 3/5 tài khoản chỉ chứng minh bảng/filter hiển thị đủ dòng; chưa đạt gate thực nghiệm 3+ roles. Bảng batch dùng đúng cases API trả về, không tự sinh Cartesian product ngoài selected mapping. Dependency còn lại: QA Browser E2E độc lập sau khi Lead tích hợp Analyze/Compare và phục vụ bundle mới. Giữ ownership frontend/report tới handoff để tránh cùng sửa file.

## Tái kiểm tra assignment 796cf21d — 2026-11-15 22:07 Việt Nam

HEAD vẫn bdbba9933ca057cb2247c3a1de9b3ee239c452bd; giữ toàn bộ diff cũ. Đã đọc README, foundation, matrix/QA audits và skill design-taste-frontend. Bản hiện tại đã có Analyze/Compare do teammate triển khai; lượt này giữ nguyên các phần ấy, không thay Compare về NOT_RUN khi đã có persisted T18 evidence.

Bổ sung riêng `frontend/src/App.tsx`: IdentityPanel đếm số tài khoản và distinct nonempty role từ identities DTO, hiển thị gate cấu hình 3/5 role, phân biệt role lab/quản trị web và ghi chưa xác minh thực nghiệm. MatrixPanel có nút “Lập ma trận”, pending/disabled, lỗi inline, empty state; bỏ kết quả request đã cũ khi đổi project/operation/resource hoặc unmount bằng generation ref. Preview không queue. CaseMatrix/resource redaction đã có được giữ nguyên.

`frontend/src/WebDemo.test.tsx`: thêm test coverage role không bằng account count; loading/error không queue; nhiều operation giữ case_key riêng, conflict UNKNOWN và role thiếu. Cập nhật tên nút trong test cũ. Các tests project-switch, resource PATCH omit/replacement, 3/5 account rows và filters vẫn PASS.

Fresh final commands tại root:

- `npm --prefix frontend test`: exit 0, **4 files / 37 tests PASS**, 8.05s, bắt đầu 22:07:41.
- `npm --prefix frontend run build`: exit 0, TypeScript + Vite; 17 modules, asset index-DUcU0a2p.js.
- `npm --prefix frontend run lint`: exit 0 (`tsc -b --noEmit`).
- `git diff --check`: exit 0.

Lỗi trung gian đã sửa: test loading click khi selection chưa sẵn sàng; TypeScript errorNotice nullable. Không bỏ test. Không sửa backend/runner/evaluator/DB hoặc api.ts/styles.css trong lượt tái kiểm tra này.

Skill: áp dụng nguyên tắc nội dung thật, form có nhãn, trạng thái thao tác rõ; không thêm landing-page hero/hiệu ứng vào workflow nghiên cứu. Visual gate/browser **NOT_RUN**: không chạy browser qua shell hoặc deploy/network trong assignment này. Chưa xác minh responsive/render thực tế. Test mock/coverage cấu hình không phải bằng chứng 3+ roles thực nghiệm. Manual/ZAP/BFLA vẫn cần evidence thật; không tự tạo kết quả. Không tác động runtime, container, Run #2, snapshots, queue/lab/ZAP, commit/push/reset. Kiểm tra automation cuối lượt: bot không có automation.
