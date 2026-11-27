# Kiểm tra và chạy lại ngày 24/11/2026

Local HEAD bdbba99; giữ nguyên working tree dirty, không pull/build/commit/reset.

Đã restart container deploy-authz-web-1 và hai user service t18-bola-lab.service, t18-bola-management.service trên SSH cuong@192.168.1.12, remote HEAD 514f978.

Lab ban đầu không khởi động: server.lock còn PID 122732 không tồn tại. Đã kiểm tra os.kill(pid,0) trả ProcessLookupError, đổi tên khóa sang bản stale-20261124-1524, rồi khởi động lại service. Không reset state, thay token hay sửa database.

Kiểm tra sau khởi động: http://127.0.0.1:8000 HTTP 200; http://100.106.64.21:5003/health HTTP 200, status ready; GET health từ container web tới lab HTTP 200.

Management service có listener 100.106.64.21:5443 nhưng HTTP trực tiếp không trả response; service được cấu hình HTTPS mTLS. Chưa kiểm chứng giao diện management bằng trình duyệt hoặc chứng chỉ client.

Không chạy matrix, xác minh token thật hoặc thay policy. Không có automation của bot tại thời điểm kiểm tra.
