# BFLA-04 — Attestation và scoped cleanup

2026-11-15. Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd` xác minh đầu lượt. **PASS regression người triển khai; QA độc lập pending; thực nghiệm NOT_RUN; tổng thể PARTIAL.**

Đọc README root/lab và bfla-audit/lifecycle/approval/proof reports. Không thấy AGENTS.md trong inventory project; báo cáo lượt trước cũng xác nhận ancestor không có. Giữ toàn bộ diff có trước. Chỉ sửa sáu file ownership bên dưới và tạo báo cáo này. Không sửa manifest/approval/cli/consumer/comparison/ba docs QA.

## Contract và threat model

Preflight mới pin SHA-256 bytes của fixed Compose trong repository. Loader reject missing/changed digest: legacy receipt vẫn là evidence lịch sử nhưng không được dùng cho lifecycle mới. Runtime yêu cầu image identity từ preflight; inspect actual container/volume và exact project/service/workflow labels, running state, loopback binding; exact single volume mount `/vampi/database`, writable, loại volume và tên `<project>_vampi_db`; volume labels phải cùng project/logical volume. Compose service config hash thực tính qua operator transport phải khớp container label (64 lowercase hex). Không suy isolation chỉ từ số lượng volume.

Prepare/execute/extended vẫn gọi runtime gate trước HTTP, giữ approval/stage/proof contracts. Không tạo operational approval. Compose path tính cố định từ source location; cleanup không chấp nhận file cùng basename ở nơi khác hoặc symlink cuối. Digest và Docker labels không phải chữ ký: local filesystem/operator/Docker daemon là trust boundary. Check/query rồi mutation vẫn có TOCTOU nếu operator ngoài workflow sửa Docker; không claim chống malicious operator hay daemon. Compose transport và inspect là dữ liệu operator; tests không gọi chúng thật.

Teardown yêu cầu preflight hợp lệ và runtime attestation trước down; không còn fallback thiếu preflight. Shared identity phải khớp trước mutation. Chỉ dùng exact project `down --volumes`, bỏ remove-orphans; không rm/prune volume tùy ý. Evidence phải nằm ngoài private directory. Claim cleanup O_EXCL + khóa lifecycle chung chống thực thi đồng thời/replay; khóa được giữ cả sau cleanup để seal run, interrupted cleanup cần operator review, không auto retry. Không chấp nhận active/interrupted stage để cleanup tự động. Đây là fail-closed policy, không crash recovery tự động.

Down failure/exception hoặc post-inspection failure giữ private directory; chỉ unlink fixed fixture secret rồi rmdir directory khi Docker sạch, không recursive delete arbitrary files. Receipt durable publish no-overwrite, fsync theo stage contract; giữ receipt/claims khi fail. Nếu attestation fail trước mutation thì không tạo teardown receipt, artifacts cũ được giữ. Nếu publish lỗi, pending/claim giữ nguyên. Shared snapshot sau cleanup khác khiến INCOMPLETE. Không đọc upstream DB; receipt ghi `upstream_database_proof: UNKNOWN`, shared identity/state không chứng minh DB unchanged. Không claim full isolation/upstream attestation. Sanitized digest DB do operator cung cấp chưa có contract trong manifest/CLI; không tự mở ownership để thêm. Muốn full proof cần ticket riêng cho provenance/binding của metadata đó.

## Fresh verification

Chạy từ root bằng `PYTHONPATH=tools/authorization-lab/src .venv/bin/python -`:

```python
import socket, subprocess
from unittest.mock import patch
import pytest
with patch.object(socket.socket, 'connect', side_effect=AssertionError('network blocked')), patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('network blocked')), patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS blocked')), patch.object(subprocess, 'Popen', side_effect=AssertionError('process blocked')), patch.object(subprocess, 'run', side_effect=AssertionError('process blocked')):
    raise SystemExit(pytest.main(['tools/authorization-lab/tests/disposable', 'tools/authorization-lab/tests/evaluation/test_bfla_evidence.py', '-q']))
```

Final exit **0**, **78 passed + 102 subtests passed in 0.82s**. Tests synthetic/temp/mocks; mismatch mount/project/image/hash/volume/missing field bị reject, cleanup gate không gọi down; failed down giữ canary và sanitized receipt; arbitrary compose path reject; missing/tampered digest reject. BFLA02/03/05 regression vẫn PASS. Lượt đầu 75 pass + 1 fail do fixture mocked preflight chưa tạo evidence parent; sửa test fixture, không nới production. Lượt kế 76/100 PASS; bổ sung hai tests rồi final trên. `git diff --check` exit **0**. Pytest-asyncio cảnh báo loop scope chưa cấu hình, ngoài ticket.

Không Docker/lab/HTTP/lifecycle thật/network/runtime/Run #2/DB/browser/login/deploy/commit/push/reset/xóa evidence lịch sử. Temp fixtures tự cleanup. Không instance được tạo, không cleanup log lab mới. Kiểm automation trước báo cáo: bot không có automation. QA độc lập, power-loss/multiprocess thực và attestation thực nghiệm chưa chạy; 3+ roles NOT_RUN, Browser E2E giữ BLOCKED.

## Hash trước/sau

SHA-256 snapshot trước thay đổi và sau verification; những file disposable còn lại giữ hash bằng nhau (11 file). Sáu file thay đổi có chủ đích:

| File | Before | After |
| --- | --- | --- |
| `tools/authorization-lab/src/authz_lab/disposable/preflight.py` | `b98e416d156404a5e09939f0ef40a617fa3812b2d6f89c47df22d4f12f23322a` | `b98eb7cbf1d6d7d476326d326181f8af2e7aab05d12f2b8dfa44c6658abc9f4e` |
| `tools/authorization-lab/src/authz_lab/disposable/runner.py` | `1d06f903814ddfe212ef055aae9c6623f8353601dba664abafed8e242176705a` | `0ebbabdd54399bcea2b878a2d5efa237b4b24e5fa6f4615b82b8401966b5a1b1` |
| `tools/authorization-lab/src/authz_lab/disposable/teardown.py` | `daf56e2528d99774d4ad7b7936398a80ec7b71661ac4e1329869c405f5c90ceb` | `fea67d29919c5c15017bf3e03e9017197410ebba4a1e713bf79d5a46a393f5eb` |
| `tools/authorization-lab/tests/disposable/test_preflight.py` | `57fb58991d2417d4f32225f1b313f1b4d78900006180eb7b261f28d8b719962c` | `afb97c1ca91c1fec51c105c8571f25b1d38edb095f031d6a8deb618606c11f80` |
| `tools/authorization-lab/tests/disposable/test_runner.py` | `b691792c1a338a3061985af656fa56f883c7751ddee0fc036298aea90bc9ff84` | `37cce480765dba0a6c4f6f669a5cdcc4bee9abe70b7525f14383623e8c73b50f` |
| `tools/authorization-lab/tests/disposable/test_teardown.py` | `bfe87af9c1f44219a71651f83732fa3b91d480b235ad0f06493cf450b765acd8` | `dd1addb75aa0965b5d3c8c635950753f82eea230bb393edd48a646f4d351b925` |
