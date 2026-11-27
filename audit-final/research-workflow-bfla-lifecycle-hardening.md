# BFLA-03 — Lifecycle replay/crash/redirect hardening

Ngày 2026-11-15. Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`.
Verdict **PASS regression người triển khai; QA độc lập pending; thực nghiệm NOT_RUN; tổng thể PARTIAL**.

Đã đọc README root/lab, bfla-audit, approval-hardening và proof-integration. Không tìm thấy AGENTS.md trong project qua rg hoặc các ancestor đã kiểm tra. Giữ mọi diff có trước. Ticket chỉ sửa disposable/runner.py, preflight.py; tạo disposable/stage.py, tests/disposable/test_stage.py và báo cáo này. Không sửa manifest/cli/approval/consumer/comparison/ba docs QA.

## Contract và bằng chứng synthetic

- Preflight, prepare, execute và execute-extended dùng khóa `.lifecycle-active` chung trong thư mục evidence của run, tạo bằng O_CREAT|O_EXCL. Stage claim riêng giữ vĩnh viễn theo run/stage, không tự phục hồi hoặc retry. Hai thread synthetic execute/extended chứng minh stage thứ hai dừng trước thân hàm; test reentrant bổ sung cùng invariant. Claim đã tồn tại sau race vẫn chặn trước mutation.
- Prepare bị KeyboardInterrupt tại request reset đầu tiên giữ khóa/claim; lần prepare tiếp theo dừng, request count vẫn 1. Bất kỳ interruption sau claim buộc dùng run mới; không cố đoán fixture đang ở trạng thái nào. Lỗi Exception lưu failure marker với literal STAGE_FAILED, không exception text/body/credential. BaseException giữ active lock để fail closed. Sau exception thường, active lock được bỏ nhưng claim của stage vẫn giữ để cấm replay.
- Public execute/extended kiểm receipt/claim hiện hữu trước approval và transport. Receipt lịch sử không được rewrite. Approval BFLA02 vẫn do operator cung cấp, xác minh và consume trước stage body; invalid approval không tạo lifecycle claim. Race loser có thể đã consume approval trước khi gặp active lock: đây là fail closed, phải dùng run mới, không tự cấp lại approval. Test public extended với approval synthetic chứng minh failure rồi replay chỉ vào runtime check một lần và không gọi transport.
- Receipt producer và preflight được publish bằng file pending O_EXCL mode 0600, fsync nội dung, hard-link cùng filesystem tới tên cuối với semantics không overwrite, rồi fsync directory. Pending hoặc claim sau crash được giữ, không xóa evidence. Existing final receipt được bảo toàn cả khi publish thất bại. Cần filesystem local hỗ trợ hard-link/fsync; lỗi filesystem dừng workflow. Đây không phải journal chống operator sửa file hoặc đảm bảo trên mọi filesystem/power-loss model.
- HTTP opener dùng redirect handler từ chối follow; transport không có retry loop. Status 30x còn được reject ngay cả khi transport trả response hoặc HTTPError trực tiếp. Synthetic transport qua opener thật chứng minh 301/302/303/307/308 không gửi request thứ hai tới redirect destination. Lỗi transport cũng chỉ gọi một lần.
- Budget BFLA02 không thay đổi. Test _request thật + transport mock kiểm extended boundary: 22 GET /me hợp scope đi qua transport; request 23 raise trước transport. Đây là boundary counter test, không phải mô phỏng đủ 22 bước một thực nghiệm extended.
- Proof BFLA05 không đổi schema/semantics; regression producer→consumer, unknown/mismatch/HTTP204 self-update vẫn PASS. Các functional tests cũ gọi __wrapped__ bỏ qua gate để kiểm proof độc lập; public runner tests kiểm gate/lifecycle riêng.

## Fresh verification

Từ project root, chạy `.venv/bin/python` với `PYTHONPATH=tools/authorization-lab/src` và chương trình dưới đây (không gọi CLI vận hành):

```python
import socket, subprocess
from unittest.mock import patch
import pytest
with patch.object(socket.socket, 'connect', side_effect=AssertionError('network blocked')), patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('network blocked')), patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS blocked')), patch.object(subprocess, 'Popen', side_effect=AssertionError('process blocked')), patch.object(subprocess, 'run', side_effect=AssertionError('process blocked')):
    raise SystemExit(pytest.main(['tools/authorization-lab/tests/disposable', 'tools/authorization-lab/tests/evaluation/test_bfla_evidence.py', '-q']))
```

Fresh final exit **0**: **73 passed, 93 subtests passed in 0.79s**. Tất cả test mới chỉ dùng TemporaryDirectory/mocks/synthetic threads; network/DNS/process thật bị chặn. Hai lượt trước khi bổ sung coverage: 69/88 rồi 71/93 đều exit 0. Pytest-asyncio có cảnh báo default loop scope chưa cấu hình, ngoài ticket. `git diff --check` sau code/tests exit **0**.

## Giới hạn và bàn giao

Không tạo approval vận hành, không chạy lifecycle thật/HTTP/lab/Docker/ZAP/runtime/DB/Run #2/deploy/commit/push/reset, không xóa evidence lịch sử. Không instance được tạo nên không có cleanup log lab hoặc attestation upstream mới. Temporary fixtures tự cleanup. Kiểm tra trước bàn giao: bot không có automation.

Local operator và filesystem vẫn là trust boundary; digest/claim không phải chữ ký hay chứng thực người phê duyệt. Không claim crash recovery tự động: interrupted run bị quarantine bằng claim/lock, operator dùng run mới. BFLA-04 actual mount/compose/image attestation và cleanup/upstream proof chain còn dependency, chưa triển khai trong ticket. QA độc lập BFLA03, thực nghiệm disposable và nghiệm thu 3+ roles chưa chạy. Không nối orchestration/web hoặc thay lịch sử Run #2.
