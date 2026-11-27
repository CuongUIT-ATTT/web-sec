# Đối chiếu mẫu Synthetic với lab SSH — 21/11/2026

Kết luận: FAIL về tương thích cấu hình; chưa chạy lại matrix hay xác minh bearer trong lượt này. Chỉ audit read-only, không sửa code/dữ liệu/lab. Local HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd (working tree có thay đổi); SSH /home/cuong/VAmPI HEAD 514f978.

Nguồn: backend/app/services/demo_seed.py; SSH openapi_specs/bola-lab.openapi.json, bola_lab/server.py, docs/bola-lab-operator-guide.vi.md. Không đọc private answer sheet hay xuất secret.

| Hạng mục | Mẫu Synthetic | Lab SSH |
|---|---|---|
| Principal pointer | /id | /principal/username |
| Book operation | GET /books/{id} | GET /books/{book_id} |
| Path parameter | id | book_id |
| Resource ID | userA-book, userB-book, admin-book | book-A1, book-A2 của userA; book-B1, book-B2 của userB |
| Resource pointer | /id | /data/id |
| Protected pointer | /secret | /data/secret |
| BFLA | GET /reports | Không có endpoint này |
| Admin policy | ALLOW mọi operation | Không có quyền ALLOW toàn cục; tài liệu khai báo UNKNOWN ngoài control |
| Credentials | Bearer mô phỏng được seed | Token lab do operator cấp |

Lưu ý: tên placeholder id/book_id có thể cùng khớp URL nếu mapping đúng, nhưng cần đồng bộ path_parameter. admin-book không có trong fixture lab. Token mẫu không dùng được trên lab SSH; token người dùng đã thay có thể hợp lệ, chưa kiểm tra lại trong lượt này.

Mẫu đã seed bốn rule owner/admin/cross-user/reports-admin-only. Ô nhập tên rule trống không chứng minh chưa lưu rule. seed_demo trả project đã có mà không cập nhật lại dữ liệu; nạp lại mẫu không đồng bộ lab.

Cấu hình phù hợp: GET /health cho connection test; GET /me với /principal/username cho từng danh tính; GET /books/{book_id} cho BOLA, mapping book_id + /data/id + /data/secret và các ID/owner đúng fixture. Dùng userB làm authorized baseline cho book-B1/B2. Không giữ rule admin ALLOW mọi thứ hoặc case /reports. Quyền cross-owner phụ thuộc policy được operator cấp, đặc biệt S08 có chia sẻ hợp lệ; không suy luận DENY chỉ vì khác owner. Scenario hiện hành và policy riêng của run chưa được xác nhận trong lượt audit này.

Lỗi khóa matrix: các sai lệch có thể gây identity mismatch, thiếu baseline, hoặc UNKNOWN_POLICY; chưa đọc state project hiện tại nên không khẳng định tất cả blocker hiện tại chỉ từ seed. Không có case_id/run_id mới; không tuyên bố nghiệm thu hay kết quả thực nghiệm.
