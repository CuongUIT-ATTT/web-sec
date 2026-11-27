# QA độc lập BFLA-03 lifecycle

Run QA-BFLA03; 2026-11-15T22:58:50.389137+07:00 (giờ Việt Nam).
HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; root `/home/cuong/Dự án/Bảo mật web/Project`.
Python 3.14.8, pytest 9.2.0, `.venv/bin/python`. Đã đọc README root/lab và lifecycle-hardening; review stage.py, runner.py, preflight.py, approval.py và compatibility proof consumer. Không có AGENTS.md trong repo/ancestor đã kiểm. Giữ mọi diff có trước.

## Fresh disposable

Command gốc: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=tools/authorization-lab/src .venv/bin/python -`.
`pytest.main(['/home/cuong/Dự án/Bảo mật web/Project/tools/authorization-lab/tests/disposable', '-q', '--tb=short', '-p', 'no:cacheprovider', '--basetemp', '/tmp/t18-qa-lifecycle-nyo82brv/disposable'])`

Exit **0**.

```text
.uuuu..uuuuuuuuuuu..uuuu...uu.uu.......uuuuuuuuu.uu............uuuu....u [ 62%]
uuuu.uuuu.uuuuuu.uuuu........uu.......uuuuu.uuuuu..                      [100%]
54 passed, 69 subtests passed in 0.47s
```

## Fresh consumer

Command gốc: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=tools/authorization-lab/src .venv/bin/python -`.
`pytest.main(['/home/cuong/Dự án/Bảo mật web/Project/tools/authorization-lab/tests/evaluation/test_bfla_evidence.py', '-q', '--tb=short', '-p', 'no:cacheprovider', '--basetemp', '/tmp/t18-qa-lifecycle-nyo82brv/consumer'])`

Exit **0**.

```text
..............uuuuuuuuuuuuuu.uu.uuuuuuuu...                              [100%]
19 passed, 24 subtests passed in 0.05s
```

Guard xuyên collection/execution: socket connect/connect_ex/sendto/create_connection/getaddrinfo, subprocess Popen/run, os.system/posix_spawn/posix_spawnp raise AssertionError; ExitStack + unittest.mock.patch. TMPDIR và tempfile.tempdir trỏ TemporaryDirectory riêng; cache/plugin autoload/bytecode tắt. Đây là Python guard, không phải sandbox OS. Temp artifacts tự cleanup; không gửi HTTP/chạy process thật.

HASH_STABILITY **True**.

## Review độc lập

- Public runner check receipt/claim trước approval/runtime; approval consume trước lifecycle body và context budget được reset trong finally. Invalid approval không cấp quyền vận hành. Replay extended và interrupted prepare bị chặn; race test thread/reentrant kiểm lifecycle decorator, không phải hai process public CLI thực. Race loser có thể đã consume approval: fail closed, dùng run mới.
- O_EXCL khóa chung và stage claim bảo toàn khi crash mô phỏng KeyboardInterrupt; Exception giữ claim và marker literal STAGE_FAILED không lộ exception/body. Không có automatic recovery. Lock/claim không có fsync directory ở mọi bước: không tuyên bố durability toàn bộ trước power-loss/kernel/filesystem crash; filesystem/operator vẫn trust boundary.
- Receipt dùng pending O_EXCL, fsync file, hard-link no-overwrite rồi fsync directory. Existing receipt được giữ; pending/claim sau lỗi không bị xóa. Chưa fault-inject mọi điểm fsync/link hoặc kill process thật.
- 301/302/303/307/308 bị chặn bởi opener thực với transport synthetic; đúng một transport attempt, HTTPError redirect và transport failure không retry.
- Extended cap 22: _request + RequestBudget thật và transport mock cho phép 22 GET /me; request 23 bị reject trước transport. Đây là counter boundary, không phải đủ chuỗi 22 thao tác extended. Scope/payload/principal bypass kiểm trong suite approval; không có approval lab thực.
- BFLA02 approval digest/run/stage/expiry/one-use giữ contract; local acknowledgement không chữ ký hay trust anchor. BFLA05 producer→consumer mock regression gồm unknown/mismatch/denied/HTTP204; functional proof tests bypass decorator được phân biệt với public-gate tests. Không attestation receipt authenticity.

## Kết luận và giới hạn

**PASS independent focused regression/mock integration BFLA-03 và compatibility BFLA-02/05.** Tổng thể **PARTIAL**. BFLA-04 attestation mount/compose/image và cleanup/upstream proof chưa triển khai/nghiệm thu. CMP-05 importer đang module riêng, CMP-05–07/API/UI ngoài QA này. Thực nghiệm manual/ZAP/BFLA và 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED**, không login lại. Lab digest/attestation **NOT_VERIFIED**; OpenAPI/fixtures hash chỉ là fixture đóng gói synthetic. Không sửa production/tests; không lab/network/runtime/DB/Run #2/Docker/browser/deploy/commit/push/reset/xóa evidence.

## SHA-256 trước = sau

| Artifact | SHA-256 |
|---|---|
| `tools/authorization-lab/src/authz_lab/disposable/__init__.py` | `bb72333fb08082622517f687a5f5acbe297a9ee755785e3e9d684c48b7147646` |
| `tools/authorization-lab/src/authz_lab/disposable/approval.py` | `8d6047bc5da97bb7d29b286d82bf61b726714a7d2fdc22c3543225b23ece417c` |
| `tools/authorization-lab/src/authz_lab/disposable/cli.py` | `a7b26b512dcb1bf2775b5f49af0f6bdc138436b210eb7a540b81874867ef843e` |
| `tools/authorization-lab/src/authz_lab/disposable/manifest.py` | `903844871cde1b21a6081cbcc9173bee235c62b341132656a57360128cdc3785` |
| `tools/authorization-lab/src/authz_lab/disposable/preflight.py` | `b98e416d156404a5e09939f0ef40a617fa3812b2d6f89c47df22d4f12f23322a` |
| `tools/authorization-lab/src/authz_lab/disposable/runner.py` | `1d06f903814ddfe212ef055aae9c6623f8353601dba664abafed8e242176705a` |
| `tools/authorization-lab/src/authz_lab/disposable/stage.py` | `c355294770cabb532e599b0279dcdd3325a8c88627077af6e2b05509fde22f5d` |
| `tools/authorization-lab/src/authz_lab/disposable/teardown.py` | `daf56e2528d99774d4ad7b7936398a80ec7b71661ac4e1329869c405f5c90ceb` |
| `tools/authorization-lab/src/authz_lab/evaluation/bfla_evidence.py` | `fdca67d22a5ba010ae21ff01b4338d2071f4cf202a022e7c87a42c988d4fae88` |
| `tools/authorization-lab/src/authz_lab/fixtures/manual_sample_cases.json` | `0ece045d34599487bfbac175e49efc3afce8f2beda4f34f67c41d39817af6eca` |
| `tools/authorization-lab/src/authz_lab/fixtures/ownership.csv` | `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f` |
| `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` | `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b` |
| `tools/authorization-lab/tests/disposable/__init__.py` | `7ceac6324541bc3a17b03843fb67ba138e8ef031d55e243823c733b428c5151d` |
| `tools/authorization-lab/tests/disposable/test_approval.py` | `65daa6617f63e56cddfa75491a92000c3d2ab2097ec5c4e2d25b6513c42047a1` |
| `tools/authorization-lab/tests/disposable/test_cli.py` | `54db6b11ebd14fae55d41c5222646904ab3e7edae1b415d9cc197b0b7289129d` |
| `tools/authorization-lab/tests/disposable/test_compose.py` | `b8d8a3d8e1bb4daabfffdc578ba90d9f3ab84e2c1b931586045a446dcdb46759` |
| `tools/authorization-lab/tests/disposable/test_manifest.py` | `fbc2055867596cefd4999ed34a2cd7c74f35af9f6e4aa451c54e1acbaa491f2b` |
| `tools/authorization-lab/tests/disposable/test_preflight.py` | `57fb58991d2417d4f32225f1b313f1b4d78900006180eb7b261f28d8b719962c` |
| `tools/authorization-lab/tests/disposable/test_runner.py` | `b691792c1a338a3061985af656fa56f883c7751ddee0fc036298aea90bc9ff84` |
| `tools/authorization-lab/tests/disposable/test_stage.py` | `0dcbbc1608d97d2b6a845ddf1aa244def493f5c5cec097e727a5040a9cc507f1` |
| `tools/authorization-lab/tests/disposable/test_teardown.py` | `bfe87af9c1f44219a71651f83732fa3b91d480b235ad0f06493cf450b765acd8` |
| `tools/authorization-lab/tests/evaluation/test_bfla_evidence.py` | `ce0201294a8359bd9d732db150fca20f37b8abd9d8a60b7092171497ac9d72f2` |

Automation check 2026-11-15T15:58:50.524Z: bot không có automation/monitor.

Revalidate 22 hashes sau cập nhật docs: PASS.
