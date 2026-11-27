# QA độc lập BFLA-04 attestation và cleanup

Run QA-BFLA04; 2026-11-15T23:09:18.222265+07:00 (giờ Việt Nam).
Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Python 3.14.8, pytest 9.2.0.

Đọc README root/lab, báo cáo bàn giao và review preflight/runner/teardown/stage; không tìm thấy AGENTS.md trong repo/ancestor. Giữ diff có trước. Lab digest/attestation thực NOT_VERIFIED; OpenAPI/fixtures bên dưới là fixture đóng gói, không chứng minh lab đang chạy.

## Fresh commands và exits

Lệnh gốc: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=tools/authorization-lab/src .venv/bin/python -`.

### disposable

`pytest.main(['/home/cuong/Dự án/Bảo mật web/Project/tools/authorization-lab/tests/disposable', '-q', '--tb=short', '-p', 'no:cacheprovider', '--basetemp', '/tmp/t18-qa-attestation-fcg2ysu5/disposable'])`

Exit **0**.

```text
.uuuu..uuuuuuuuuuu..uuuu...uu.uu.......uuuuuuuuu.uu.....uu........uuuu.. [ 54%]
..uuuuu.uuuu.uuuuuu.uuuu.....uuuuuuu....uu.......uuuuu.uuuuu.....        [100%]
59 passed, 78 subtests passed in 0.74s
```

### consumer

`pytest.main(['/home/cuong/Dự án/Bảo mật web/Project/tools/authorization-lab/tests/evaluation/test_bfla_evidence.py', '-q', '--tb=short', '-p', 'no:cacheprovider', '--basetemp', '/tmp/t18-qa-attestation-fcg2ysu5/consumer'])`

Exit **0**.

```text
..............uuuuuuuuuuuuuu.uu.uuuuuuuu...                              [100%]
19 passed, 24 subtests passed in 0.11s
```

Guard xuyên collection/execution: socket connect/connect_ex/sendto/create_connection/getaddrinfo; subprocess Popen/run; os.system/posix_spawn/posix_spawnp bị chặn bằng AssertionError. Đây là Python guard, không phải OS sandbox. Temp riêng; plugin autoload/cache/bytecode tắt. Không Docker/HTTP/process thật. Temp synthetic tự cleanup.

HASH_STABILITY **True**, 23 artifacts.

## SHA-256 trước = sau

| Artifact | SHA-256 |
|---|---|
| `deploy/labs/vampi-bfla-disposable.compose.yaml` | `4436663ddd9327dd65bf3b57250bcb0790869c4822d2fec6eb6361ff37f17372` |
| `tools/authorization-lab/src/authz_lab/disposable/__init__.py` | `bb72333fb08082622517f687a5f5acbe297a9ee755785e3e9d684c48b7147646` |
| `tools/authorization-lab/src/authz_lab/disposable/approval.py` | `8d6047bc5da97bb7d29b286d82bf61b726714a7d2fdc22c3543225b23ece417c` |
| `tools/authorization-lab/src/authz_lab/disposable/cli.py` | `a7b26b512dcb1bf2775b5f49af0f6bdc138436b210eb7a540b81874867ef843e` |
| `tools/authorization-lab/src/authz_lab/disposable/manifest.py` | `903844871cde1b21a6081cbcc9173bee235c62b341132656a57360128cdc3785` |
| `tools/authorization-lab/src/authz_lab/disposable/preflight.py` | `b98eb7cbf1d6d7d476326d326181f8af2e7aab05d12f2b8dfa44c6658abc9f4e` |
| `tools/authorization-lab/src/authz_lab/disposable/runner.py` | `0ebbabdd54399bcea2b878a2d5efa237b4b24e5fa6f4615b82b8401966b5a1b1` |
| `tools/authorization-lab/src/authz_lab/disposable/stage.py` | `c355294770cabb532e599b0279dcdd3325a8c88627077af6e2b05509fde22f5d` |
| `tools/authorization-lab/src/authz_lab/disposable/teardown.py` | `fea67d29919c5c15017bf3e03e9017197410ebba4a1e713bf79d5a46a393f5eb` |
| `tools/authorization-lab/src/authz_lab/evaluation/bfla_evidence.py` | `fdca67d22a5ba010ae21ff01b4338d2071f4cf202a022e7c87a42c988d4fae88` |
| `tools/authorization-lab/src/authz_lab/fixtures/manual_sample_cases.json` | `0ece045d34599487bfbac175e49efc3afce8f2beda4f34f67c41d39817af6eca` |
| `tools/authorization-lab/src/authz_lab/fixtures/ownership.csv` | `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f` |
| `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` | `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b` |
| `tools/authorization-lab/tests/disposable/__init__.py` | `7ceac6324541bc3a17b03843fb67ba138e8ef031d55e243823c733b428c5151d` |
| `tools/authorization-lab/tests/disposable/test_approval.py` | `65daa6617f63e56cddfa75491a92000c3d2ab2097ec5c4e2d25b6513c42047a1` |
| `tools/authorization-lab/tests/disposable/test_cli.py` | `54db6b11ebd14fae55d41c5222646904ab3e7edae1b415d9cc197b0b7289129d` |
| `tools/authorization-lab/tests/disposable/test_compose.py` | `b8d8a3d8e1bb4daabfffdc578ba90d9f3ab84e2c1b931586045a446dcdb46759` |
| `tools/authorization-lab/tests/disposable/test_manifest.py` | `fbc2055867596cefd4999ed34a2cd7c74f35af9f6e4aa451c54e1acbaa491f2b` |
| `tools/authorization-lab/tests/disposable/test_preflight.py` | `afb97c1ca91c1fec51c105c8571f25b1d38edb095f031d6a8deb618606c11f80` |
| `tools/authorization-lab/tests/disposable/test_runner.py` | `37cce480765dba0a6c4f6f669a5cdcc4bee9abe70b7525f14383623e8c73b50f` |
| `tools/authorization-lab/tests/disposable/test_stage.py` | `0dcbbc1608d97d2b6a845ddf1aa244def493f5c5cec097e727a5040a9cc507f1` |
| `tools/authorization-lab/tests/disposable/test_teardown.py` | `dd1addb75aa0965b5d3c8c635950753f82eea230bb393edd48a646f4d351b925` |
| `tools/authorization-lab/tests/evaluation/test_bfla_evidence.py` | `ce0201294a8359bd9d732db150fca20f37b8abd9d8a60b7092171497ac9d72f2` |

## Review độc lập và giới hạn

- Runtime gate yêu cầu image preflight; exact một container và volume `<project>_vampi_db`, project/service/workflow labels, image, running state, loopback port, Compose config hash 64 hex, volume labels và exact writable volume mount `/vampi/database`. Missing/malformed inspect bị fail closed. Loader pin SHA-256 bytes fixed Compose; missing/changed digest reject. Prepare/execute/extended gọi gate trước `_request`; teardown gọi gate trước `down`.
- Synthetic runtime matrix kiểm valid/mount/project/image/hash/missing Mounts/wrong volume label. Cleanup gate test mismatch chặn transport trước down. Chưa có test từng missing field đi qua từng public stage; không coi helper test là toàn bộ public integration.
- Teardown chỉ fixed Compose/project `down --volumes`, không remove-orphans/rm/prune/recursive delete. Evidence phải ngoài private run directory; chỉ unlink fixed secret rồi rmdir, file lạ làm rmdir fail. Wrong Compose path reject. Failed down giữ canary, private directory và receipt; stdout/stderr SECRET canary không vào receipt. Pre-mutation attestation failure không tạo teardown receipt nhưng giữ evidence cũ.
- Lifecycle cleanup claim/active lock O_EXCL và durable_json no-overwrite giữ claims/pending khi lỗi; cleanup seal không tự retry. Compatibility BFLA02 approval/run/stage/digest/expiry/one-use, BFLA03 redirect/replay/crash/race/budget22 và BFLA05 proof producer/consumer đều regression PASS. Một số functional proof tests bypass decorator; public gate coverage tách biệt. Chưa fault-inject cleanup tại mọi điểm os.open/fsync/link hoặc chạy multiprocess/kill/power-loss thực.
- Upstream DB không được đọc, `upstream_database_proof: UNKNOWN`; shared identity/state unchanged không chứng minh DB unchanged. `TEARDOWN_COMPLETE` chỉ nghĩa scoped cleanup theo contract, không phải full isolation/DB proof. Provenance/digest metadata DB còn dependency ngoài ownership. Hash/labels/operator inspect không phải chữ ký hay attestation độc lập; filesystem/operator/daemon là trust boundary, query→mutation có TOCTOU.

## Kết luận

**PASS independent focused synthetic regression/mock integration BFLA-04; compatibility BFLA02/03/05 PASS.** 59 tests + 78 subtests disposable và 19 tests + 24 subtests consumer, từng exit 0: tổng **78 tests + 102 subtests**. Không có regression failure trong lượt này. Tổng thể **PARTIAL**: provenance DB còn dependency; CMP05 API/store, CMP06/UI, CMP07 chưa nối/nghiệm thu. Không có ground truth thực mới. Thực nghiệm manual/ZAP/BFLA và 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED**, không yêu cầu login lại.

Không sửa production/tests; không lab/network/runtime/DB/Run #2/Docker/browser/login/deploy/commit/push/reset/xóa evidence lịch sử. Chỉ báo cáo này và ba docs trạng thái được ghi. Automation kiểm 2026-11-15T16:09:18.398Z: bot không có automation/monitor.

Revalidate 23 hashes sau cập nhật docs: PASS. `git diff --check` exit **0**.
