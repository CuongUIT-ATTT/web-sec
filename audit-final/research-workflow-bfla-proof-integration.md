# BFLA-05 — Producer/consumer proof integration

Ngày 2026-11-15; root `/home/cuong/Dự án/Bảo mật web/Project`.
HEAD xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`.
Verdict **PASS regression; thực nghiệm NOT_RUN; tổng thể PARTIAL**.

Đã đọc README gốc/lab, audit BFLA, report BFLA-01 và BFLA-05, producer và consumer hiện tại. Không có AGENTS.md trong inventory project hay các ancestor đã kiểm tra. Giữ mọi diff có sẵn. Chỉ sửa runner.py, tests/disposable/test_runner.py và báo cáo này; không sửa consumer/comparison hay ba tài liệu QA.

## Contract và thay đổi

Mỗi DELETE đã thực hiện nay có operation.proof gồm baseline {status:200, username, fresh:true}, principal {status, username, admin:bool} và postcondition {status, username, path}. Baseline lấy từ profile đã được _require_profile xác minh ngay trước DELETE; status 200 là điều kiện bắt buộc của helper đó. Principal là metadata allowlist trả về trực tiếp từ /me sau kiểm tra exact identity/boolean role, không suy từ outcome hoặc secret fixture. Actor dùng response role validation hiện có; admin control dùng response /me kiểm tra lại trước DELETE hiện có.

Postcondition dùng chính profile read sau DELETE: valid matching profile là 200, exact absence là 404; invalid/malformed/mismatched read có status null và state null. Không thêm HTTP request. Target username/path trong postcondition là đích manifest của observation, không phải claim profile trả về đúng khi unknown. Operation admin chưa chạy giữ status/state null và không có proof. Không xuất token, email, password, raw body hoặc extra response fields.

Schema_version giữ 1; proof là trường bổ sung. Consumer hiện tại đã chấp nhận contract này. Legacy receipt thiếu proof tiếp tục INCONCLUSIVE, không migrate/rewrite history. Extended không có thay đổi semantics: helper principal/role giờ trả metadata nhưng caller extended không dùng return. Không sửa receipt authenticity, digest, approval, cleanup hoặc importer.

## Regression synthetic và kết quả mới

Fixture run_id `a1b2c3d4` là synthetic trong TemporaryDirectory riêng, tự cleanup; không là evidence thực nghiệm. Test integration gọi runner với HTTP mock và consumer `_build_findings` thật; đường positive/denied/unknown còn đọc receipt JSON đã serialize để đối chiếu result trước khi chuyển consumer.

- DELETE 204 + fresh baseline + exact 404: BFLA_CONFIRMED_DESTRUCTIVE; 5 request mock, không tăng so với producer trước thay đổi.
- Non-admin 401 + victim tồn tại; admin 200 + control absent: DENIED_CONTROL; 9 request mock.
- GET401/500/malformed200/principal khác hoặc victim vẫn sống: INCONCLUSIVE.
- Principal mismatch trước write: exception, không receipt và chỉ 1 GET mock.
- Receipt producer bị đổi summary/principal/baseline freshness/postcondition: consumer INCONCLUSIVE.
- Redaction: kiểm tra secret-key guard, fixture token không xuất và positive receipt không chứa email.

Fresh commands từ root:

1. `PYTHONPATH=tools/authorization-lab/src .venv/bin/python -m pytest tools/authorization-lab/tests/disposable tools/authorization-lab/tests/evaluation/test_bfla_evidence.py -q`
   Exit **0**, `50 passed, 56 subtests passed in 0.38s`. Các suite lifecycle chỉ dùng mock hiện có; không chạy lifecycle thật.
2. Final focused verification dưới global network/process guards (ngoài guard trong test):

```python
import socket
import subprocess
from unittest.mock import patch
import pytest
with patch.object(socket.socket, 'connect', side_effect=AssertionError('network blocked')), patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('network blocked')), patch.object(subprocess, 'Popen', side_effect=AssertionError('process blocked')), patch.object(subprocess, 'run', side_effect=AssertionError('process blocked')):
    raise SystemExit(pytest.main(['tools/authorization-lab/tests/disposable/test_runner.py', 'tools/authorization-lab/tests/evaluation/test_bfla_evidence.py', '-q']))
```

   Chạy bằng `PYTHONPATH=tools/authorization-lab/src .venv/bin/python -`.
   Exit **0**, `38 passed, 47 subtests passed in 0.27s`.
3. `git diff --check`: exit **0**.

Có warning pytest-asyncio chưa cấu hình default fixture loop scope, ngoài ownership. Không có failure trong các lệnh verification trên.

## Giới hạn và dependencies

BFLA-02 vẫn thiếu manifest/approval provenance/stage/hash/expiry/one-use và enforced budget; BFLA-03 vẫn thiếu no-redirect/atomic stage claims/replay/race/crash và immutable failure receipts; BFLA-04 vẫn thiếu actual mount/compose/image attestation cùng cleanup/upstream proof chain. Không dùng proof metadata mới như cryptographic authenticity hoặc attestation thực nghiệm. Consumer độc lập cần QA review lại integration này.

Không gọi lab/HTTP/Docker/Compose/lifecycle thật, runtime/Run #2/DB/results lịch sử; không deploy/commit/push/reset/xóa evidence. Không tạo instance nên không có cleanup log lab mới hoặc bằng chứng upstream runtime mới. Temporary fixtures được cleanup bởi unittest; network/process guard chứng minh suite này không kết nối hoặc khởi chạy process thật, không chứng minh isolation của một lần chạy lab. Thực nghiệm và gate 3+ roles NOT_RUN. Đã kiểm tra automation: bot không có automation.
