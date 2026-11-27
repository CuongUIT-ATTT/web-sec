# BFLA-02 — Manifest/stage-bound local operator approval

Ngày 2026-11-15. Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD xác minh mới `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`.
Verdict: **PASS deterministic regression; thực nghiệm NOT_RUN; tổng thể PARTIAL**.

Đã đọc README root/lab, audit BFLA và proof-integration; không có AGENTS.md trong project/ancestor được kiểm tra. Giữ diff có sẵn, gồm runner/test_runner của BFLA-01/05; git diff tổng không chỉ là thay đổi ticket này. Chỉ sửa manifest.py, cli.py, runner.py và tests tương ứng, tạo approval.py/test_approval.py và báo cáo này. Không sửa consumer/comparison/QA docs.

## Contract

Manifest mới schema 2 có execution_scopes độc lập `execute` và `execute-extended`: exact method/path, tập payload fields, request_cap 9 và 22. Canonical scope không cho operator nới cap hoặc thêm operation. Digest SHA-256 trên canonical JSON ràng buộc toàn bộ manifest và scope. Schema 1 vẫn đọc/validate cho lịch sử nhưng không được thực thi; không rewrite artifact.

CLI cả hai stage bắt buộc `--approval <file>` và `--approval-digest <64 lowercase hex>`; không có lệnh tự approve, không tạo approval từ create-manifest hay từ yêu cầu sửa code. API runner cũng mặc định từ chối thiếu approval. File acknowledgement được operator cung cấp, schema chính xác:

- schema_version: integer 1; run_id; stage (`execute` hoặc `execute-extended`).
- manifest_digest và scope_digest: SHA-256 canonical JSON (sort_keys=True, separators=(',', ':'), allow_nan=False).
- issued_at/expires_at: Unix seconds hữu hạn, không bool; issued_at <= now < expires_at, validity tối đa 3600 giây.
- nonce: 32 lowercase hex; operator: alias 1–64 ký tự chữ/số/underscore/hyphen.
- provenance: literal `local-operator-acknowledgement`.

Digest của toàn record phải khớp digest operator nhập riêng. Không xuất credential/raw response hay payload vào approval claim. Record không có unknown fields. Thiếu/sai run, manifest, scope, stage, expiry, provenance hoặc digest bị reject trước runtime check, secret load, HTTP và claim mutation. Không có operational approval nào được tạo trong lượt này.

Sau validation, exclusive O_EXCL claim `.execute-approval-used` hoặc `.execute-extended-approval-used` trong run directory giữ digest, mode 0600, flush/fsync. Stage đã claim bị từ chối dùng lại, kể cả sau lỗi preflight/runtime. Claim giữ nguyên khi lỗi: không tự retry hay tái cấp approval. Đây là one-use theo run/stage, không phải registry chứng thực nonce toàn hệ thống.

Context-local budget bao toàn bộ lời gọi _request của stage, tính cả GET baseline/principal, login và probes. Chặn exact path/method/payload field set không thuộc stage trước transport; POST login/register kiểm tra username thuộc fixture run, register chỉ escalated + admin=true. Budget exhausted không gọi transport thêm. Redirect tự động bị từ chối vì nếu follow thì có thể vượt cap mà không qua counter; không thêm retries. Prepare vẫn giữ workflow riêng, không kế thừa execution scope.

BFLA-05 receipt/proof không đổi contract và không thêm request. Regression cũ gọi phần thân qua `__wrapped__` để kiểm semantics độc lập với gate; test mới riêng gọi public runner với approval thật synthetic và consumer thật. Điều này tách rõ functional proof tests và approval integration, không dùng mock approval làm bằng chứng gate.

## Threat model và compatibility

Đây là acknowledgement cục bộ do operator chủ động cung cấp cùng digest độc lập. **Không có trust anchor, không chữ ký xác thực, không chứng minh một người ngoài hệ thống đã phê duyệt**. Kẻ có quyền điều khiển cả file và digest CLI hoặc sửa code/run directory nằm trong local operator trust boundary và có thể giả mạo acknowledgement. Digest chỉ phát hiện sửa record so với giá trị operator đã review/pin; không chứng minh danh tính. Không coi bot message hay task code/tests là authorization thực nghiệm.

Breaking change có chủ đích: caller execute/execute_extended phải cung cấp hai keyword approval/approval_digest; CLI cũ thiếu flag dừng ở parser. Legacy manifest không được dùng cho writes. Reader lịch sử và proof consumer vẫn đọc theo contract cũ. Không migrate hay sửa results.

BFLA-03 vẫn thiếu state machine/lock chung giữa execute và extended, crash recovery cho prepare, append-only failure receipts và chống race toàn lifecycle; exclusive approval claim chỉ giải quyết one-use stage này. Redirect blocker là thay đổi tối thiểu cần để cap không bị implicit follow-up bypass, không claim BFLA-03 hoàn tất. BFLA-04 vẫn thiếu actual mount/compose/image attestation và cleanup/upstream proof chain. Approval không thay preflight hoặc lab attestation.

## Fresh deterministic verification

Fixtures đều synthetic trong TemporaryDirectory; không phải evidence lab. Tests phủ missing/stale/future/wrong-stage/wrong-run/tampered manifest/scope/digest/provenance; replay sau failure; legacy read-only; exact cap và rejection trước transport; extended principal/payload ngoài scope; redirect rejection; CLI required inputs/forwarding; approved producer → consumer confirmed proof. Regression BFLA-01/05 còn phủ unknown, denied, mismatch và HTTP204 self-update.

Lệnh đầu: `PYTHONPATH=tools/authorization-lab/src .venv/bin/python -m pytest tools/authorization-lab/tests/disposable tools/authorization-lab/tests/evaluation/test_bfla_evidence.py -q` — exit 0, **56 passed, 71 subtests passed** (trước thêm CLI/redirect regression).

Final verification từ root, `PYTHONPATH=tools/authorization-lab/src .venv/bin/python -` với nội dung:

```python
import socket
import subprocess
from unittest.mock import patch
import pytest
with patch.object(socket.socket, 'connect', side_effect=AssertionError('network blocked')), patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('network blocked')), patch.object(subprocess, 'Popen', side_effect=AssertionError('process blocked')), patch.object(subprocess, 'run', side_effect=AssertionError('process blocked')):
    raise SystemExit(pytest.main(['tools/authorization-lab/tests/disposable', 'tools/authorization-lab/tests/evaluation/test_bfla_evidence.py', '-q']))
```

Exit **0**, **61 passed, 81 subtests passed in 0.45s**. Global guards chặn network/process thật; tests lifecycle chỉ mock, không vận hành lifecycle. Pytest-asyncio cảnh báo default loop scope hiện chưa cấu hình, ngoài ticket. `git diff --check` chạy riêng sau final tests: exit **0**. `git rev-parse HEAD`: exit **0**, giá trị trên.

Không gọi HTTP/lab/Docker/Compose/lifecycle thật, không runtime/Run #2/DB/deploy/commit/push/reset/xóa evidence. Không instance được tạo nên không có cleanup log lab hoặc attestation upstream mới. Temporary fixtures tự cleanup. Bot không có automation khi kiểm tra trước bàn giao. QA độc lập và thực nghiệm/3+ roles vẫn chưa nghiệm thu.
