# QA độc lập CMP-03, BFLA-02 và producer–consumer BFLA-05

Run QA-OBSERVATIONS-APPROVAL; 2026-11-15T22:46:17.563373+07:00 (giờ Việt Nam).
Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd` đã kiểm tra. Python 3.14.8, pytest 9.2.0, `.venv/bin/python`. Giữ mọi diff hiện có. Không tìm thấy AGENTS.md trong repo và ancestor đã kiểm tra. Đọc README root/lab, reports observations/approval-hardening/proof-integration và QA trước; review observations, approval, manifest/CLI/runner và consumer diff/source cùng tests.

**PASS independent focused regression/mock integration cho CMP-03, BFLA-02 và BFLA-05; tổng thể PARTIAL. Tổng 82 tests + 257 subtests PASS; tất cả 4 pytest exit 0. Không skip/xfail được báo.**

## Fresh execution

Command: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=tools/authorization-lab/src .venv/bin/python -`.
Wrapper dùng `pytest.main` riêng từng target dưới `TemporaryDirectory(prefix='t18-qa-observations-approval-')`, đặt TMPDIR/tempfile.tempdir vào đó; cache/bytecode/plugin autoload tắt. `unittest.mock.patch` chặn socket connect/connect_ex/create_connection/getaddrinfo/sendto, subprocess Popen/run, os.system/posix_spawn/posix_spawnp xuyên collection/execution. Guard là kiểm thử Python, không phải sandbox OS. Tests có mocks nội bộ, không gửi HTTP hay chạy lifecycle/process thật. Temp artifacts tự cleanup; không output lab mới. Source/tests/fixtures được hash trước–sau, HASH_STABILITY **True**.

### observations

`pytest.main(['/home/cuong/Dự án/Bảo mật web/Project/tools/authorization-lab/tests/evaluation/test_observations.py', '-q', '--tb=short', '-p', 'no:cacheprovider', '--basetemp', '/tmp/t18-qa-observations-approval-1byefp75/observations'])`

```text
uuu....uuuuuuuuuu..uuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuu.uuuuuuuuuuuu.uuuuuu [ 81%]
uuuuuuuuuuuuuuuu..uuuuuuu.                                               [100%]
11 passed, 87 subtests passed in 0.11s

```

Fresh exit: **0**.

### case_manifest

`pytest.main(['/home/cuong/Dự án/Bảo mật web/Project/tools/authorization-lab/tests/evaluation/test_case_manifest.py', '-q', '--tb=short', '-p', 'no:cacheprovider', '--basetemp', '/tmp/t18-qa-observations-approval-1byefp75/case_manifest'])`

```text
uuu.uuuuuuuuuuu..uuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuu.uuuuuuu.uuuuuu [ 60%]
uuuuuuuuuuuuuuuu.uuuu.uu...                                              [100%]
10 passed, 89 subtests passed in 0.06s

```

Fresh exit: **0**.

### bfla_evidence

`pytest.main(['/home/cuong/Dự án/Bảo mật web/Project/tools/authorization-lab/tests/evaluation/test_bfla_evidence.py', '-q', '--tb=short', '-p', 'no:cacheprovider', '--basetemp', '/tmp/t18-qa-observations-approval-1byefp75/bfla_evidence'])`

```text
..............uuuuuuuuuuuuuu.uu.uuuuuuuu...                              [100%]
19 passed, 24 subtests passed in 0.06s

```

Fresh exit: **0**.

### disposable

`pytest.main(['/home/cuong/Dự án/Bảo mật web/Project/tools/authorization-lab/tests/disposable', '-q', '--tb=short', '-p', 'no:cacheprovider', '--basetemp', '/tmp/t18-qa-observations-approval-1byefp75/disposable'])`

```text
.uuuu..uuuuuuuuuuu..uuuu...uu.uu.......uuuuuuuuu.uu............uuuu....u [ 80%]
uuuu.uuuu.uuuuuu.uuuu......                                              [100%]
42 passed, 57 subtests passed in 0.35s

```

Fresh exit: **0**.

## Review và ranh giới kết luận

- CMP-03: exact manifest digest/version, case membership/revision, actor/owner không join bằng path; duplicate/malformed/mismatch bị reject. MANUAL automated verifier khác HUMAN; `human_observation_verified` chỉ là metadata gate, không kiểm bytes/hash artifact, danh tính người hay ground truth. ZAP ILLEGAL/LEGAL giữ UNKNOWN; NOT_RUN/INVALID/UNKNOWN/BLOCKED không trở thành negative. Legacy UNLINKED. Provenance authenticity, importer/catalog resolution và orchestration chưa nghiệm thu.
- BFLA-02: canonical manifest v2 tách execute/extended, scope/cap 9 và 22; approval pin digest + run/stage/manifest/scope/expiry, local acknowledgement không chữ ký/trust anchor. Invalid approval bị reject trước preflight/secret/HTTP và không tạo claim. O_EXCL claim giữ sau failure; replay cùng run/stage bị chặn. Context budget ở _request kiểm exact operation/payload/principal trước transport, cả khi allow_extended_scope=True; redirect bị reject. CLI bắt operator cấp approval + digest, không tự approve. Legacy schema 1 chỉ đọc. Đây không phải authorization vận hành hay attestation lab.
- BFLA-05: runner lấy proof từ baseline/principal/postcondition responses đã kiểm; không thêm request và không lấy proof từ summary. Synthetic producer → serialized receipt → consumer thật bao phủ positive/denied/unknown/mismatch. Functional runner tests dùng __wrapped__ để cô lập semantics; approval test riêng gọi public decorated runner với synthetic approval, không tính các test bypass decorator là kiểm gate. Unknown/malformed/survivor/contradictory summary không confirmed. Không chứng thực receipt authenticity hoặc cleanup.
- BFLA-03–04 còn thiếu global lifecycle locking/race/crash recovery/failure receipt và actual mount/image/compose attestation/cleanup proof. One-use theo run/stage không phải global nonce registry; local operator kiểm soát file và digest nằm trong trust boundary. Không mở rộng PASS sang concurrency/crash/attestation.
- CMP-04 đang được owner làm module riêng, ngoài QA này. CMP-04–07, importer/API/UI và experiment benchmark chưa nghiệm thu. Không có TP/FP/FN hay timing thực nghiệm từ mock; chưa linked Run #2 hoặc ground truth đã review.

Unit/focused regression và mock producer–consumer integration được phân loại riêng với live runtime/E2E. Thực nghiệm manual/ZAP/BFLA, 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED** do người dùng từ chối đăng nhập, không yêu cầu lại. Tổng thể **PARTIAL**. Không sửa production/tests; không lab/network/DB/runtime/Run #2/Docker/deploy/commit/push/reset/xóa evidence. Lab image digest/attestation **NOT_VERIFIED**; fixture/policy/case_id đều synthetic theo test name, không fixture runtime.

## SHA-256 trước/sau

| Artifact | SHA-256 (trước = sau) |
|---|---|
| `tools/authorization-lab/src/authz_lab/disposable/__init__.py` | `bb72333fb08082622517f687a5f5acbe297a9ee755785e3e9d684c48b7147646` |
| `tools/authorization-lab/src/authz_lab/disposable/approval.py` | `8d6047bc5da97bb7d29b286d82bf61b726714a7d2fdc22c3543225b23ece417c` |
| `tools/authorization-lab/src/authz_lab/disposable/cli.py` | `a7b26b512dcb1bf2775b5f49af0f6bdc138436b210eb7a540b81874867ef843e` |
| `tools/authorization-lab/src/authz_lab/disposable/manifest.py` | `903844871cde1b21a6081cbcc9173bee235c62b341132656a57360128cdc3785` |
| `tools/authorization-lab/src/authz_lab/disposable/preflight.py` | `4b6159c11ca07deeea21e31b58fa5e990a378cce9c67d7ed87d6591889a7a11d` |
| `tools/authorization-lab/src/authz_lab/disposable/runner.py` | `7e83b7f2ce417f2067867e763473399f130eb101d898be945475f50a0cb629c0` |
| `tools/authorization-lab/src/authz_lab/disposable/teardown.py` | `daf56e2528d99774d4ad7b7936398a80ec7b71661ac4e1329869c405f5c90ceb` |
| `tools/authorization-lab/src/authz_lab/evaluation/bfla_evidence.py` | `fdca67d22a5ba010ae21ff01b4338d2071f4cf202a022e7c87a42c988d4fae88` |
| `tools/authorization-lab/src/authz_lab/evaluation/case_manifest.py` | `38fb21fecc9b6a40dbc558a38b0f9e99956e76dfc1701903de0d638b9d8f9fb3` |
| `tools/authorization-lab/src/authz_lab/evaluation/observations.py` | `72cda5b6d69603672392ef913382e3920ddf7213d5fb9f9432263f17823bcf69` |
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
| `tools/authorization-lab/tests/disposable/test_teardown.py` | `bfe87af9c1f44219a71651f83732fa3b91d480b235ad0f06493cf450b765acd8` |
| `tools/authorization-lab/tests/evaluation/test_bfla_evidence.py` | `ce0201294a8359bd9d732db150fca20f37b8abd9d8a60b7092171497ac9d72f2` |
| `tools/authorization-lab/tests/evaluation/test_case_manifest.py` | `be03ad6c3a672c1c606067c67d6a0942870598b39f77db54854116c14368c5ea` |
| `tools/authorization-lab/tests/evaluation/test_observations.py` | `1228e6dbebeb01d13a39a910d954aefe464a9744f4d9fe82ce5ba237671158ee` |

Automation check: bot không có automation/monitor, xác minh 2026-11-15T15:45:39.668Z.

## Giới hạn bao phủ cần giữ

Public approved producer–consumer positive test mock `_request`, vì vậy kiểm decorator/claim/proof propagation nhưng không tự kiểm budget qua transport trong cùng test đó. Scope/cap/rejected-before-transport được test riêng qua `_request` với transport mock (execute cap 9); extended payload/principal có test riêng, nhưng không có boundary test tiêu hết cap 22 trong suite hiện tại. Không nâng kết quả thành complete transport integration hoặc concurrency/crash acceptance. Các lỗi I/O approval không hợp lệ có thể nổi dưới ValueError/OSError thay vì cùng một thông báo CLI; vẫn dừng trước HTTP, chưa nghiệm thu trải nghiệm lỗi CLI toàn bộ.

Kiểm tra cuối: `git diff --check` exit 0. Revalidate toàn bộ source/tests/fixture hashes từ bảng sau cập nhật docs: exit 0. Chỉ ghi report này và prepend cập nhật vào ba docs được giao; không sửa nội dung lịch sử.
