# SSH-SEED-01 — triển khai profile cấu hình SSH

Ngày 21/11/2026. Trạng thái: PARTIAL / chờ Lead và QA độc lập; không tuyên bố COMPLETE.

## Phạm vi và nguồn

HEAD trước sửa: `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Working tree đã dirty rộng; demo_seed.py và test_demo_seed.py đã là untracked khi nhận việc. Không commit/push/reset. Chỉ sửa test_demo_seed.py, thêm ssh_seed.py và báo cáo này. Không sửa demo_seed.py, frontend, route, CLI authorization-lab hoặc file dirty khác.

Đối chiếu contract từ `audit-final/synthetic-ssh-compatibility-20261121.md` (Lead ghi nhận SSH 514f978). Lượt này không SSH, không đọc answer sheet, không gọi API lab hoặc chạy matrix thật; không xác nhận scenario hiện hành.

## Thay đổi

- `backend/app/services/ssh_seed.py`: `seed_ssh(session, settings, project_id=None)` tạo profile riêng hoặc chuyển dự án mẫu đã biết sang cấu hình SSH. `main()` cung cấp lệnh áp dụng ngoài giao diện. Hàm không HTTP, không tạo/giải mã/sửa credential; caller commit/rollback.
- Target cố định lab được cấp phép `http://100.106.64.21:5003`, vẫn qua scope validation hiện có; verification path `/me`, principal `/principal/username`.
- Chỉ chọn `GET /books/{book_id}`. Mapping riêng `ssh-book`: `/data/id`, `/data/secret`, parameter `book_id`. Fixture `book-A1/A2 → userA`, `book-B1/B2 → userB`.
- Chỉ rule `ssh-owner: ALLOW OWNER`. Không admin ALLOW toàn cục; không DENY cross-owner suy diễn. Cross-owner/admin giữ UNKNOWN đến khi có scenario policy. `/reports` và operation cũ được deselect, không nằm trong revision mới.
- Giữ nguyên resource, operation và revision cũ để bảo toàn liên kết lịch sử; không xóa dữ liệu mẫu cũ. Mỗi profile mới thêm revision riêng, không sửa revision trước. Vì vậy Setup vẫn có thể thấy fixture/operation cũ nhưng chúng không thuộc active authorization profile SSH.
- Target/principal đổi thì append kết quả verification `NOT_RUN`, reason `SSH_PROFILE_REQUIRES_REVERIFICATION`; không xóa kết quả xác minh cũ. Cần xác minh lại từng tài khoản. Reapply không tiếp tục invalidate nếu mapping/target không đổi.
- Từ chối dự án không đúng seed đã biết, nhiều target, danh tính ngoài 3 role, run chưa kết thúc và scope không cho phép. Nếu policy mới hơn đang active nhưng revision SSH đã có trong lịch sử thì fail closed thay vì ghi đè. Caller phải rollback khi lỗi.
- Synthetic local và nút nạp synthetic giữ nguyên hành vi; nút này không phải nút chuyển SSH. Profile SSH được áp dụng bằng lệnh riêng, không tự động chạy qua nút nạp mẫu.

## Đã áp dụng vào web đang phục vụ cổng 8000

Container `deploy-authz-web-1`, database `/var/lib/authz/authz-web.sqlite3` (không phải database `data/` trên host). Đọc trạng thái trước sửa: project 3 tên `T18 Synthetic GET Demo v1`, target 3 trỏ lab SSH, không có run active. Project 1 và project 2 (`Test`) không chỉnh sửa.

Đã copy duy nhất module ssh_seed.py vào `/app/backend/app/services/ssh_seed.py` trong container và gọi `seed_ssh(..., project_id=3)` với Settings đang dùng của container; không restart web hoặc lab. Code nguồn trên host đã có module cho build sau này. File copy trong container sẽ mất khi recreate nếu image chưa rebuild; cấu hình DB nằm trong volume nên vẫn giữ.

Trước sửa tạo SQLite backup nhất quán bằng SQLite backup API: `/var/lib/authz/ssh-seed-01-before.sqlite3`, mode 0600. Backup chứa credential mã hóa; không xuất ra báo cáo/attachment. Không tự restore backup vì sẽ làm mất dữ liệu phát sinh sau đó.

Sau commit mở session mới đọc lại:

- Active authorization revision ID 4: `e504ab72b365d7179c20d599444bec47fac9d6f31759d1ec603e6c5d0307d8cf`.
- Ba principal pointer đều `/principal/username`.
- Operation được chọn duy nhất `GET /books/{book_id}`.
- Bốn ID/owner/parameter và hai response pointer đúng như trên.
- So sánh toàn bộ row trước/sau các bảng `identity_secrets`, `runs`, `run_results`, `run_identity_secrets`, `findings`, `finding_reproductions`, `comparison_bundles`: giữ nguyên. Không in giá trị credential hoặc evidence.
- Preview thực tế sau chuyển: `0 executable`; identity 6,7,8 đều `IDENTITY_NOT_VERIFIED`. Đây là invalidation có chủ đích, chưa phải lỗi lab.

## Kiểm thử

Lệnh: `.venv/bin/python -m pytest backend/tests/test_demo_seed.py backend/tests/test_authorization_model.py -q`

Kết quả cuối: **18 passed, 1 warning, 6.80s**. Warning Starlette/httpx deprecation; pytest cũng thông báo cấu hình asyncio fixture scope chưa đặt.

Bổ sung 3 test: chuyển profile giữ credential/history và idempotent; tạo mới không credential giả và chặn active run; từ chối scope/dự án khác. Test synthetic cũ vẫn đạt, gồm GET/matrix/run/results và idempotence.

Test cô lập dùng fixture verification mô phỏng để kiểm tra policy, không phải evidence chạy lab: 3 danh tính × 4 resource = 12 case; 4 owner executable; 8 UNKNOWN có UNKNOWN_POLICY; mọi baseline là owner. Kiểm tra live chỉ đọc preview sau chuyển, không queue run, chưa có case_id/run_id thực nghiệm mới.

## Cách dùng sau bàn giao

Dự án 3 đã được chuyển: refresh trang, chọn lại project 3, xác minh admin/userA/userB bằng token lab đã nhập, rồi tạo lại preview. Không cần nạp lại synthetic. Token hiện có giữ nguyên byte mã hóa; token hết hạn hoặc token synthetic cũ sẽ cần operator thay bằng token lab hợp lệ. Chỉ owner cases có policy đã xác định; cần scenario policy chính thức trước khi chạy cross-owner/admin, không chọn ALLOW ANY để mở khóa.

Để tạo profile mới sau khi build image chứa module, chạy trong môi trường đã có AUTHZ_* của web:

```bash
python -m backend.app.services.ssh_seed
```

Để chuyển một dự án synthetic đã biết khác (đọc ID trước, không đoán):

```bash
python -m backend.app.services.ssh_seed --project-id <ID>
```

Không truyền secret qua command line. Module đọc Settings từ môi trường; không tự sửa scope hay settings. Nút synthetic tiếp tục phục vụ lab local. Nếu operator đã chỉnh scenario rules sau chuyển, không rerun profile để thay policy đang dùng.

Chưa xác minh: token thực trên lab, scenario/permission cross-owner/admin, trình duyệt hiển thị sau refresh và QA độc lập. Lead cần review trước khi tuyên bố nghiệm thu.
