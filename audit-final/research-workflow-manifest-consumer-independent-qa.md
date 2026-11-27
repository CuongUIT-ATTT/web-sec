# QA độc lập CMP-02 và consumer BFLA-05

**CMP-02 và BFLA-05 consumer PASS independent focused regression; tổng thể PARTIAL.**

Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Timestamp 2026-11-15T22:43:33.554779+07:00 (giờ Việt Nam). Python 3.14.8, pytest 9.2.0, `.venv/bin/python`. Giữ mọi diff có sẵn. Đọc README root/lab và ba report case-manifest, bfla-evidence-hardening, bfla-proof-integration; review toàn bộ hai production modules và tests, diff consumer với HEAD. Không thấy AGENTS.md trong repo và các ancestor đã kiểm tra.

## Inventory và ranh giới

Run QA-MANIFEST-CONSUMER; fixtures và policy synthetic theo test method (case_id kiểm thử là tên test), không phải run thực nghiệm. OpenAPI/ownership đóng gói được hash bên dưới, không chứng thực fixture runtime. Lab image digest/attestation NOT_VERIFIED: không gọi lab hoặc Docker. Consumer test import build_manifest hiện tại để dựng fixture thuần; không chạy disposable suite, producer integration hoặc lifecycle. Hash manifest dependency cũng được ghi trước/sau.

## Fresh execution

Command: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=tools/authorization-lab/src .venv/bin/python -` với wrapper Python dùng `pytest.main` riêng từng file:

```python
with tempfile.TemporaryDirectory(prefix='t18-qa-manifest-consumer-') as tmp, contextlib.ExitStack() as stack:
    stack.enter_context(patch.dict(os.environ, {'TMPDIR': tmp}))
    tempfile.tempdir = tmp
    for name in ['socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
                 'socket.getaddrinfo', 'subprocess.Popen', 'subprocess.run', 'os.system',
                 'os.posix_spawn', 'os.posix_spawnp']:
        stack.enter_context(patch(name, side_effect=AssertionError('QA external IO blocked')))
    for name in ['case_manifest', 'bfla_evidence']:
        code = pytest.main([f'tools/authorization-lab/tests/evaluation/test_{name}.py',
                            '-q', '--tb=short', '-p', 'no:cacheprovider',
                            '--basetemp', str(Path(tmp) / name)])
```

Wrapper còn capture stdout/stderr, timestamp, hashes trước/sau và propagate failure exit; imports standard library, pytest, unittest.mock.patch. Plugins autoload tắt; cache và bytecode tắt; artifact chỉ ở temp riêng. Network/DNS/process thật bị block xuyên collection/execution; test có mock nội bộ. Không skip/xfail được báo.

### case_manifest

```text
uuu.uuuuuuuuuuu..uuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuu.uuuuuuu.uuuuuu [ 60%]
uuuuuuuuuuuuuuuu.uuuu.uu...                                              [100%]
10 passed, 89 subtests passed in 0.07s
```

Fresh pytest exit: **0**.

### bfla_evidence

```text
..............uuuuuuuuuuuuuu.uu.uuuuuuuu...                              [100%]
19 passed, 24 subtests passed in 0.07s
```

Fresh pytest exit: **0**.

## Review contract và limitations

- CMP-02: frozen scalar definitions/tuple cohort; canonical JSON SHA-256, order independence và golden vector; mọi semantic revision đổi identity/version. Reject duplicates/conflicting scenarios, missing/unknown/tampered fields, invalid enum/type/template và unknown membership. Aliases opaque theo format; static path/role vẫn cần upstream review để bảo đảm không chứa identifier thật. Digest là content identity, không chữ ký/ground truth. Chưa chứng minh importer/UI/orchestration đã nối hoặc historical/Run #2 mapping.
- BFLA-05 consumer: exact boolean state và exact integer postcondition 404, fresh matching 200 baseline, đúng principal/boolean role, run/workflow/target/path là điều kiện proof. Legacy thiếu proof, null/missing/malformed/survivor/read401/read500 và summary mâu thuẫn giữ INCONCLUSIVE. Positive và denied controls chỉ là synthetic proof. Consumer không xác thực nguồn receipt/hash/approval/cleanup; extended passthrough chưa nghiệm thu. Comment “producer currently omits proof” trong consumer đã cũ so với producer handoff; không sửa production và không dùng comment để kết luận producer.
- Producer integration và runner final review **PENDING independent QA**, đúng phạm vi yêu cầu. Không chạy tests/disposable hoặc nghiệm thu BFLA-02 approval/budget, dù owner đã báo regression. BFLA-03–04 lifecycle/replay/race/crash/attestation/cleanup còn thiếu.
- CMP-03 có owner handoff, **IN PROGRESS / pending independent review**; CMP-04–07 và importer/cohort orchestration chưa nghiệm thu. Không tính TP/FP/FN/benchmark từ mocks hoặc provenance chưa chứng thực.
- Unit/focused regression PASS ở phạm vi trên; live runtime và E2E NOT_RUN lượt này. Browser E2E vẫn BLOCKED do người dùng từ chối đăng nhập, không yêu cầu lại. Manual/ZAP/BFLA và gate 3+/5 roles thực nghiệm NOT_RUN. Tổng thể PARTIAL; không thay đổi Run #2.

Không HTTP/lab/network/lifecycle/subprocess thật, DB/runtime/results lịch sử, browser/login/full web/deploy/commit/push/reset/xóa evidence. Chỉ ghi report này và ba tài liệu trạng thái QA; không sửa production/tests.

## SHA-256 trước/sau

HASH_STABILITY: **True**.

| Artifact | SHA-256 |
|---|---|
| `tools/authorization-lab/src/authz_lab/evaluation/case_manifest.py` | `38fb21fecc9b6a40dbc558a38b0f9e99956e76dfc1701903de0d638b9d8f9fb3` |
| `tools/authorization-lab/src/authz_lab/evaluation/bfla_evidence.py` | `fdca67d22a5ba010ae21ff01b4338d2071f4cf202a022e7c87a42c988d4fae88` |
| `tools/authorization-lab/tests/evaluation/test_case_manifest.py` | `be03ad6c3a672c1c606067c67d6a0942870598b39f77db54854116c14368c5ea` |
| `tools/authorization-lab/tests/evaluation/test_bfla_evidence.py` | `ce0201294a8359bd9d732db150fca20f37b8abd9d8a60b7092171497ac9d72f2` |
| `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` | `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b` |
| `tools/authorization-lab/src/authz_lab/fixtures/ownership.csv` | `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f` |
| `tools/authorization-lab/src/authz_lab/fixtures/manual_sample_cases.json` | `0ece045d34599487bfbac175e49efc3afce8f2beda4f34f67c41d39817af6eca` |
| `tools/authorization-lab/src/authz_lab/disposable/manifest.py` | `903844871cde1b21a6081cbcc9173bee235c62b341132656a57360128cdc3785` |

Automation check cuối lượt: không có automation/monitor của bot cần dừng (2026-11-15T15:43:34.024Z).

Kiểm tra cuối: `git diff --check` exit 0; revalidate toàn bộ 8 hashes và block mới của ba tài liệu trạng thái exit 0. Wrapper suite exit 0, từng pytest exit 0.
