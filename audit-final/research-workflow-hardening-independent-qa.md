# QA-HARDEN-06 — kiểm chứng độc lập

**CMP-01/BFLA-01 PASS independent regression; tổng thể PARTIAL.**

Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD thực tế `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Giữ mọi diff. Đã đọc README root/lab, hai báo cáo comparison-hardening và bfla-hardening, diff/source comparison.py, timing.py, runner.py và tests tương ứng. Không thấy AGENTS.md trong repo và các thư mục cha đã kiểm tra.

## Execution manifest

Run kiểm chứng QA-HARDEN-06; không phải run thực nghiệm/Run #2. Timestamp suite: 2026-11-15T22:25:36.283419+07:00 (giờ Việt Nam). Toolchain `.venv/bin/python`: Python 3.14.8, pytest 9.2.0. Fixture synthetic theo test method; TemporaryDirectory riêng. Không dùng credential hoặc response thật.

Lab digest NOT_VERIFIED: không gọi lab/Docker để attestation. Compose chỉ tham chiếu tag vampi-week1:local, không coi tag là immutable digest. OpenAPI và fixtures tham chiếu đóng gói có hash dưới đây, không coi là runtime fixtures được attested.

## Fresh commands và exit

Lệnh thực chạy từ root có dạng sau; wrapper còn in timestamp/toolchain, tính SHA-256 trước/sau các nguồn/fixtures và in HASH_STABILITY:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/authorization-lab/src .venv/bin/python - <<'PY'
import contextlib, os, tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
with tempfile.TemporaryDirectory(prefix='t18-qa-harden-06-') as tmp:
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {'TMPDIR':tmp,'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}))
        tempfile.tempdir=tmp
        for name in ['socket.socket.connect','socket.socket.connect_ex','socket.create_connection','socket.getaddrinfo','subprocess.Popen','subprocess.run','os.system']:
            stack.enter_context(patch(name,side_effect=AssertionError('QA-HARDEN-06 external IO blocked')))
        for label,args in [('CMP-01/evaluation excluding pending consumer',['tools/authorization-lab/tests/evaluation','--ignore=tools/authorization-lab/tests/evaluation/test_bfla_evidence.py']),('BFLA-01/disposable',['tools/authorization-lab/tests/disposable'])]:
            print('SUITE',label,flush=True)
            code=pytest.main(args+['-q','--tb=short','-p','no:cacheprovider','--basetemp',str(Path(tmp)/('evaluation' if label.startswith('CMP') else 'disposable'))])
            print('SUITE_EXIT',int(code),flush=True)
PY
```

| Suite | Fresh output | Pytest exit | Verdict |
|---|---|---|---|
| evaluation, bỏ consumer test_bfla_evidence.py | 35 passed, 4 subtests passed in 0.17s | 0 | PASS isolated regression |
| disposable | 26 passed, 23 subtests passed in 0.17s | 0 | PASS isolated regression |
| BFLA-05 consumer | NOT_RUN independent QA | — | pending consumer review |
| Live runtime/E2E | NOT_RUN lượt này | — | Browser vẫn BLOCKED sau từ chối đăng nhập |
| Manual/ZAP/BFLA và gate thực nghiệm 3+/5 roles | NOT_RUN | — | chưa nghiệm thu |

Wrapper process exit 0; verdict dựa trên từng SUITE_EXIT, không dùng wrapper exit che failure. Không có skip/xfail/failure được báo. 35 khác owner 51 vì chủ động bỏ consumer đang ngoài phạm vi; không suy failure từ số tests của các lượt source khác nhau.

Socket/DNS/process bị chặn toàn lượt pytest; tests có mocks nội bộ thay blockers. Đã đọc tests lifecycle: fake Docker/HTTP, không thực thi lifecycle hoặc subprocess thật. Bytecode/cache tắt, artifacts tạm tự dọn bởi TemporaryDirectory. Không full web tests, browser/login, HTTP/lab/ZAP, queue, DB runtime, deploy/commit/push/reset; không đọc secret, sửa production hoặc results lịch sử.

## Review findings

1. CMP-01 PASS regression: không còn fallback 12/2 hay hidden-200 claim. Absence/malformed observations giữ null; functional evidence độc lập timing. Direct/legacy timing được validate, boolean/NaN/infinity/âm bị reject. Invalid current không fallback legacy; adjacent discovery không tìm parent run. Manual hợp lệ vẫn COMPLETED_NO_TIMING khi thiếu/invalid timing. ZAP/BFLA payload sai/mâu thuẫn fail-closed trong phạm vi summary validation đã test.
2. BFLA-01 PASS regression: GET 401/403/500, malformed hoặc principal sai giữ unknown. Exact 404 sau baseline hợp lệ mới chứng minh absence; HTTP200 + survivor INCONCLUSIVE. Principal/role mismatch chặn writes; password probe có rejection control và xác minh victim principal; HTTP204 self-update không thành write-BOLA. Receipt synthetic có redaction canary assertions.
3. BFLA-05 pending: owner bàn giao không đồng nghĩa independent PASS. Không QA file/test consumer trong lượt này. Runner schema_version 1 chưa xuất đầy đủ baseline/principal/postcondition proof cho consumer mới; cần producer–consumer integration review, receipt thiếu proof phải INCONCLUSIVE.
4. Importer/cohort thiếu: observations và timing không chứng minh run/policy/fixture alignment, ground truth, TP/FP/FN hoặc benchmark; summary validation không phải receipt attestation.
5. BFLA-02–04 còn thiếu: manifest/approval/budget; redirect/replay/race/crash/immutable receipts/bounds; volume/mount/cleanup/digest attestation. Mocks không xác minh các bảo vệ runtime này. BFLA-06 và 3+ roles thực nghiệm NOT_RUN.

Không thấy failure trong hai suite được giao; không nâng thành toàn hệ thống PASS. Case IDs là tên từng test method; fixtures/policy trong tests là synthetic, không phải policy runtime được nghiệm thu.

## Artifact hashes

SHA-256 trước/sau suite khớp tất cả: HASH_STABILITY True.

| Artifact | SHA-256 |
|---|---|
| `tools/authorization-lab/src/authz_lab/evaluation/comparison.py` | `b68e948c19c8b125d8f7aa4557e6e17f1ee7a2d3b0fadaa31623e46a0377bcfe` |
| `tools/authorization-lab/src/authz_lab/evaluation/timing.py` | `f7635d43394b0ae3a03299a1c9e775b586c0cd1d88a9421539cebe84611bad92` |
| `tools/authorization-lab/src/authz_lab/disposable/runner.py` | `dd1f1fc9fe4674d4a136f899771a08a43b84c10084fe20a8e3935673104f0c32` |
| `tools/authorization-lab/tests/evaluation/test_comparison.py` | `9a9947177ab20aa939e1fa3b5a1d8b60651a57916f320b9ba778a83af21fe252` |
| `tools/authorization-lab/tests/evaluation/test_timing.py` | `87dd48fd071b06a67b89771d150201fb6a66283d406c8a5a82e1fb9f76fd4a59` |
| `tools/authorization-lab/tests/disposable/test_runner.py` | `e56f38c683de27e915bc844a919e95f29c4e52a60a444a11398f4edcf8c1c17c` |
| `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` | `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b` |
| `tools/authorization-lab/src/authz_lab/fixtures/ownership.csv` | `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f` |
| `tools/authorization-lab/src/authz_lab/fixtures/manual_sample_cases.json` | `0ece045d34599487bfbac175e49efc3afce8f2beda4f34f67c41d39817af6eca` |

Automation cuối lượt: bot không có automation cần dừng. Ownership chỉ báo cáo này và ba tài liệu trạng thái; không tạo/sửa báo cáo audit khác.

Kiểm tra ghi tài liệu: hai command ghi/kiểm tra report lỗi heredoc delimiter (exit 2 và 1), Python lỗi trước khi ghi; không phải failure suite. Đã sửa delimiter và ghi/kiểm tra lại thành công. `git diff --check` sau tạo báo cáo: exit 0.
