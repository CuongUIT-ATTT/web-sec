# PROJECT-DELETE — triển khai ngày 2026-11-24

Trạng thái: PASS kiểm thử tự động; NOT_RUN triển khai SSH và thao tác trình duyệt/WebView thực tế.

Baseline đã đọc: HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd. Working tree có nhiều thay đổi và file chưa track từ trước; giữ nguyên, không reset/commit/push. Không tìm thấy AGENTS.md trong cây dự án hay các thư mục cha. Không xóa dự án thật, không gọi quản trị lab hay đổi trạng thái lab.

## File của ticket

- `backend/app/api/schemas.py`: DTO ProjectDelete, tên xác nhận bắt buộc.
- `backend/app/api/routes.py`: DELETE /api/projects/{project_id}, require_csrf (bao gồm admin authentication); cải thiện thông báo conflict tại create/update_identity.
- `backend/app/services/project_deletion.py`: delete_project; BEGIN IMMEDIATE trên SQLite trước kiểm tra ownership/run, khóa writer đến commit. Chặn mọi run chưa terminal và external job chưa xác định hoàn tất (UNKNOWN cũng chặn). Yêu cầu tên chính xác, phân biệt hoa thường. Tính phạm vi qua FK khai báo rồi xóa thứ tự con trước cha trong một transaction; exception đóng session sẽ rollback.
- `frontend/src/api.ts`: deleteProject qua request hiện có, giữ credentials và CSRF.
- `frontend/src/App.tsx`: DeleteProject với tên, cảnh báo cấu hình/token/comparison/evidence và không thể hoàn tác, hủy, pending lock, hiển thị lỗi. Chỉ bỏ dự án khỏi danh sách sau HTTP thành công; bỏ chọn dự án, unmount workflow và xóa state/cache hiện hành kể cả xóa dự án cuối. Tăng projectGeneration để response refresh cũ không ghi lại dữ liệu.
- `backend/tests/test_project_deletion.py`: graph toàn bộ bảng liên quan, FK enforcement/check, scope dự án khác, auth/CSRF, tên sai, run queued, job running, 404, credential được giải phóng sau xóa.
- `frontend/src/ProjectDelete.test.tsx`: tên chính xác, cảnh báo, hủy, conflict giữ dự án, thành công mới callback.
- `frontend/src/App.test.tsx`: thêm mock và kiểm thử xóa dự án cuối trở về workspace trống. Các thay đổi cũ trong file được giữ nguyên.

## Nguyên nhân conflict danh tính/token

Identity có unique(project_id, display_name), đúng scope tên theo dự án. IdentitySecret.fingerprint có unique toàn hệ thống; cùng token không thể dùng cho danh tính thứ hai kể cả ở dự án khác. Thông báo cũ gộp hai nguyên nhân gây hiểu nhầm rằng tạo dự án mới luôn giải quyết được. Giữ ràng buộc schema hiện có, không nới uniqueness hoặc migration mù quáng; thông báo mới nêu rõ cả hai scope và hướng sửa danh tính hiện có/token riêng. Test chứng minh cùng tên khác dự án được phép với token khác; token giống bị 409 và dùng lại được sau khi xóa dự án chứa token. Không trả fingerprint/token trong lỗi.

## Kiểm thử thực chạy

- `.venv/bin/pytest -q backend/tests/test_project_deletion.py backend/tests/test_workflow_api.py`: 3 passed.
- `.venv/bin/pytest -q backend/tests`: 246 passed, 1 warning (Starlette/httpx deprecation); pytest-asyncio có cảnh báo fixture loop scope chưa cấu hình.
- `cd frontend && npm test -- --reporter=dot`: 7 files, 65 passed (trước khi thêm case App xóa dự án cuối).
- `cd frontend && npm test -- src/App.test.tsx src/ProjectDelete.test.tsx --reporter=dot`: 2 files, 8 passed sau bổ sung case cuối.
- `cd frontend && npm run build`: PASS TypeScript và Vite; chạy sau khi thêm component/tests xác nhận xóa. Bổ sung cuối chỉ thay test, không đổi production.
- `git diff --check`: PASS.

Lượt chạy đầu của test backend mới thiếu các tham số Settings bắt buộc: đã sửa fixture và các lượt trên đạt. Một lần tạo file test frontend dùng nhầm đường dẫn tương đối khi cwd đã ở frontend, shell báo không có thư mục; đã tạo tại đúng đường dẫn và chạy lại thành công.

## Phạm vi và hạn chế

Evidence hiện hành lưu trong SQLite (run_results, findings/reproductions, batch claims/stats, comparison_bundles, project_authorization_revisions); graph test đã seed và kiểm tra xóa các bảng này. Xóa không quét filesystem, không xóa file export bên ngoài, evidence CLI, dữ liệu lab hay BridgeNonce không thuộc dự án. Cảnh báo UI nói rõ phạm vi này.

Chưa kiểm thử cạnh tranh đa connection bằng stress test; cơ chế khóa dựa trên single-process SQLite đang dùng. Chưa kiểm thử browser thật, visual/responsive hay WebView/mTLS; frontend dùng jsdom, không tuyên bố browser acceptance. Không dùng ứng dụng chạy thật để xóa thử. Lead/QA cần review độc lập trước deploy. Tên/token uniqueness toàn hệ thống được giữ có chủ ý; nếu sản phẩm muốn cho phép cùng token giữa dự án thì cần quyết định thiết kế và migration riêng.

Đã kiểm tra automation của bot: không có monitor/automation nào cần dừng.
