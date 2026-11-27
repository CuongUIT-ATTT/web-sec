# SSH-SEED-BUTTON-01

Đã sửa và áp dụng hotpatch web cổng 8000 ngày 24/11/2026. HEAD bdbba99; working tree dirty từ trước, không commit/reset.

Nút Nạp dữ liệu mẫu gọi POST /api/demo/ssh-seed. Tạo profile SSH riêng với URL http://100.106.64.21:5003, userA/userB/admin, GET /books/{book_id}, resource type ssh-book, /data/id, /data/secret, book-A1/A2 của userA và book-B1/B2 của userB. Không credential giả, không HTTP đến lab, không queue run. Chỉ owner ALLOW, cross-owner/admin UNKNOWN đến khi operator bổ sung policy. Nạp lại chỉ chọn dự án đã có, giữ cấu hình/lịch sử; không migrate dự án synthetic hiện hữu.

Kiểm chứng: backend/tests/test_demo_seed.py: 10 passed; frontend/src/App.test.tsx: 6 passed; npm run build đạt. HTTP web 8000 trả 200, bundle index-DwRIaTn1.js chứa endpoint SSH; POST chưa đăng nhập trả 401. Chưa bấm nút trên trình duyệt hoặc xác minh token/response SSH. Chưa QA độc lập; không tuyên bố nghiệm thu nghiên cứu R1–R8.

Triển khai: copy đúng demo_routes.py, ssh_seed.py và frontend/dist vào deploy-authz-web-1 rồi restart web; không restart/sửa lab. Backup code/UI trước thay đổi: /app/ssh-seed-button-backup-20261124 trong container. Hotpatch mất khi recreate; source host đã cập nhật cho build sau. Không thay dữ liệu database trong lượt triển khai.
