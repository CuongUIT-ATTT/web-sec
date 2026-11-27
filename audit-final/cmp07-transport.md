# CMP07-TRANSPORT-01 / CMP07-CANCEL-RECEIPT-01 — bàn giao triển khai

@T18 Lead / @T18 QA Evidence: PASS regression người triển khai, chờ QA độc lập; runtime/experiment NOT_RUN, tổng thể PARTIAL. HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd, 2026-11-16 UTC+07.

## Ownership và cách dùng

Chỉ sửa `tools/authorization-lab/src/authz_lab/evaluation/bounded_adapter.py`; tạo `bounded_http.py`, `adapter_journal.py` cùng thư mục và `tools/authorization-lab/tests/evaluation/test_bounded_http.py`. Tạo evidence `audit-final/cmp07-transport*`. Không sửa owner khác, docs trạng thái chung, không commit/push, không truy cập lab/runtime/Run #2/login/discovery.

`BoundedHTTP(origin, paths, credentials, cap=..., timeout=..., body_limit=...)` nối vào `BoundedAdapter.run(transport, journal=ExecutionJournal(path, execution_id))`. Credentials là mapping principal alias → Authorization value do operator cung cấp; không login hay tự xác minh principal. Numeric loopback HTTP only, không DNS/localhost/HTTPS; exact path/origin, GET, một connection mỗi dispatch, không retry/redirect/proxy; biến môi trường proxy không được đọc. Cap riêng transport reserve trước await/connect, adapter giữ total/phase caps. Transport cần dùng cap/body_limit/timeout không lớn hơn approval tương ứng; adapter còn enforce độc lập.

HTTP header giới hạn 8192 bytes; yêu cầu Content-Length, từ chối transfer encoding/chunked và content encoding khác identity, từ chối declared oversize trước body. Streaming read giới hạn n và remaining; premature EOF invalid. Header/read timeout, adapter timeout tổng request; close abort socket ngay không đợi peer. Chỉ HTTP 200 được xét JSON; phát hiện và sửa 204 có body bị xét trước đây. Không log header/body/credential/exception.

Journal opt-in: reserve O_EXCL mode 0600, fsync file và directory; ghi ATTEMPTING trước dispatch bằng atomic replace + fsync. CANCELLED/FAILED/COMPLETED terminal có counts và execution_id; completed có result digest. `adapter.terminal_receipt` tồn tại sau external cancellation dù CancelledError vẫn propagate. Receipt terminal là sidecar vận hành, không phải observation envelope/schema2 mới. `recover()` đóng reservation nonterminal thành CRASH_RECOVERED, không chạy request; mọi lần run dùng lại path bị FileExistsError trước dispatch. Phải giữ journal và dùng cùng một path ổn định cho execution; tự xóa hoặc đổi path không được bảo vệ bởi journal này.

## Evidence và lệnh

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/authorization-lab/src .venv/bin/python -m pytest -q -p no:cacheprovider tools/authorization-lab/tests/evaluation
git diff --check
sha256sum -c audit-final/cmp07-transport-sha256.txt
```

Regression exit 0: **161 tests + 392 subtests PASS**, 1.80s; diff-check exit 0. Log `cmp07-transport-regression.log`; bốn hashes source/test `cmp07-transport-sha256.txt`. Warning pytest asyncio fixture scope unset còn tồn tại. Không chạy wrapper cũ vì wrapper chặn listener/process và sẽ ghi đè evidence trước.

- `test_server_caps_and_statuses`: ephemeral 127.0.0.1 server counter khớp transport count và adapter counts; total cap 2 dừng ở 2, phase identity cap 1 dừng ở 1. 200, 204, 301/302/303/307/308, 401/403/500; redirect không follow (counter không tăng ngoài sequence). Environment proxy trỏ TEST-NET không đổi routing, explicit proxy/retry reject.
- `test_bounds`: chunked/gzip/oversize reject, header stall/read stall timeout, disconnect, 200 error JSON không CONFIRMED; counter 4 khớp reservations, active socket set rỗng và server handlers kết thúc.
- `test_rejections`: URL ngoài origin, redirect/retry option reject trước connection/count.
- `test_cancel_receipt_and_recovery`: task.cancel tại fake get/read/close → receipt CANCELLED counts [1,0,0], rerun reject; crash journal recovery không replay.
- `test_real_socket_cancel`: server loopback nhận đúng 1 request, cancel khi body stall → peer EOF, transport active rỗng, journal CANCELLED; không còn handler I/O.
- `test_process_crash_no_replay`: child process reserve + ATTEMPTING rồi os._exit(73); parent recover CRASH_RECOVERED giữ counts [1,0,0], adapter rerun không dispatch. Không phải crash giữa request lab thật.

## Giới hạn / gate QA

Không có claim deadline cứng khi event loop/OS/disk bị treo; asyncio cooperative và fsync có thể block. Socket abort không tạo background cleanup task. Chunked/compression/HTTPS không hỗ trợ, fail closed; cần contract riêng nếu target yêu cầu. Crash accounting là attempted reservation (có thể count trước khi socket gửi), không chứng minh server nhận request trong cửa sổ crash; không tự replay để bù. Chưa fault inject power loss/fsync failure, double cancellation, journal symlink/tampering hoặc restart với path khác. Journal path phải thuộc operator, một execution một path; sidecar chưa có consumer validation/schema2 binding, không thay observation receipt và không dùng để kết luận BOLA.

QA cần kiểm lại code/test, hashes và regression độc lập. Whole-body metadata thuộc CMP07-WHOLEBODY-01, không sửa trong ticket này. Chưa có verified runtime principals/current approval/truth nên CMP07 thực nghiệm NOT_RUN; không tuyên bố runtime PASS. Không có automation cần dừng (đã kiểm).
