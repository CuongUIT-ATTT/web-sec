# CMP-04 — QA độc lập metrics và exports

**PASS independent focused regression; tổng thể PARTIAL.**

Run ID `QA-CMP04-20261115-225221`; timestamp 2026-11-15T22:52:21+0700; timezone Asia/Ho_Chi_Minh (UTC+07). Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd` xác minh trực tiếp. Working tree có diff sẵn được giữ nguyên. Đã đọc README root/lab, report metrics-exports, source metrics.py/exports.py và tests; không tìm thấy AGENTS.md trong repo hoặc các thư mục cha đã kiểm tra. Python 3.14.8, pytest 9.2.0 từ `.venv`; không cài dependencies. Lab digest/attestation NOT_VERIFIED, không kiểm runtime. OpenAPI/fixture SHA-256 ở bảng dưới; fixture/case/policy của regression là synthetic, không phải cohort thực đã review.

## Fresh commands và exits

Chạy từ root bằng `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/authorization-lab/src .venv/bin/python -` với wrapper Python. Wrapper tạo `TemporaryDirectory(prefix='qa-cmp04-')`, đặt TMPDIR và tempfile.tempdir vào đó; mỗi suite gọi riêng:

```python
pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp', tmp+'/'+name,
             f'tools/authorization-lab/tests/evaluation/test_{name}.py'])
```

`name` lần lượt là metrics, exports, observations, case_manifest. Trong mỗi lần chạy, ExitStack + unittest.mock.patch chặn bằng AssertionError các entry points: socket.socket.connect/connect_ex/sendto, socket.create_connection/getaddrinfo/gethostbyname/gethostbyname_ex, subprocess.Popen, os.system/posix_spawn/posix_spawnp/fork. Guards là in-process test isolation, không phải OS sandbox. Không chạy disposable suite. Wrapper hash source/tests/fixtures trước và sau, exit **0** chỉ khi mọi suite exit 0 và toàn bộ hashes khớp.

| Suite | Tests | Subtests | Exit |
|---|---:|---:|---:|
| metrics | 6 | 35 | 0 |
| exports | 4 | 48 | 0 |
| observations | 11 | 87 | 0 |
| case_manifest | 10 | 89 | 0 |
| Tổng | 31 | 259 | 0 |

Có pytest-asyncio deprecation warning do chưa đặt asyncio_default_fixture_loop_scope; không có failure. Thời gian từng suite: 0.24s, 0.16s, 0.12s, 0.06s.

## Review và giới hạn

- TP/FP/FN/TN chỉ xuất khi observation COMPLETED, có provenance, truth reviewed quyết định và prediction quyết định qua đủ bốn boolean gates (source/baseline/protected-field/policy). Review/validation refs và hashes chỉ được kiểm cấu trúc; module không đọc artifact bytes hay xác thực người review. `human_observation_verified` metadata không phải attestation, ACCESS_ALLOWED hoặc ZAP ILLEGAL không tự tạo prediction.
- Tests kiểm đủ bốn confusion cells (mỗi cell 1), precision/recall/accuracy 0.5 trên synthetic fixture; đây là expected test assertions, không phải metrics thực nghiệm. NOT_RUN/INVALID/UNKNOWN/BLOCKED, unverified/unreviewed/unknown truth/prediction bị excluded kèm reason, không biến thành TN/FN. Denominator 0 trả None và CSV để trống.
- Exact manifest digest/version + case revision và observation digest bind execution; explicit selection một execution/method, không lấy latest. Missing execution có reason EXECUTION_MISMATCH; duplicate/unknown/mismatch/malformed bị reject. Same-path actors giữ case riêng.
- CSV/Markdown/evidence index giữ thống nhất case/method/execution/hash; formula prefix với whitespace được escape, Markdown escape HTML/pipe/backtick/backslash/newline. Artifact refs chỉ opaque, không resolve paths; raw operation/resource/body không export. Safety vẫn phụ thuộc caller không đưa secret giả dạng symbolic label.
- `MetricsResult` public constructor kiểm cấu trúc/coverage, không tái chứng minh eligibility từ source; chỉ kết quả evaluate với evidence upstream được review mới có ý nghĩa nghiệp vụ. Chưa có trust anchor, artifact authentication hay ground truth thật đã review. Không nâng synthetic boolean assertions thành xác nhận thực nghiệm.

CMP-04 đạt regression độc lập trong phạm vi pure contract. CMP-05–07, importer/API/UI/orchestration comparison và chứng thực provenance thực còn thiếu/chưa nghiệm thu. BFLA-03 owner đang làm, ngoài phạm vi; không chạy disposable hay nâng trạng thái lifecycle. Manual/ZAP/BFLA thực nghiệm, 3+/5 roles **NOT_RUN**. Browser E2E **BLOCKED**, không yêu cầu đăng nhập lại. Run #2/runtime/DB/lab/Docker không tác động. Không sửa production/tests, commit/push/reset hoặc xóa evidence.

## SHA-256 trước = sau (11 artifacts)

| Artifact | SHA-256 |
|---|---|
| `tools/authorization-lab/src/authz_lab/evaluation/metrics.py` | `8993b5d23ed004f60ceea8807d744adb6cf32cc273a4cc31af785d7f5b687642` |
| `tools/authorization-lab/src/authz_lab/evaluation/exports.py` | `ec4b03631399a6db3810e0261eb0c51a806cbaf5e04c0480ea313f1cf9145b1b` |
| `tools/authorization-lab/src/authz_lab/evaluation/observations.py` | `72cda5b6d69603672392ef913382e3920ddf7213d5fb9f9432263f17823bcf69` |
| `tools/authorization-lab/src/authz_lab/evaluation/case_manifest.py` | `38fb21fecc9b6a40dbc558a38b0f9e99956e76dfc1701903de0d638b9d8f9fb3` |
| `tools/authorization-lab/tests/evaluation/test_metrics.py` | `4b4a7d4c1cb56eb374c35be5ef1ccd53ee99d9a7bac8121740f1976c1e12b58b` |
| `tools/authorization-lab/tests/evaluation/test_exports.py` | `1d09b1710d8d9007bdbc1b5a6f58382b041d6931a615d06eef38f6e66a0cc795` |
| `tools/authorization-lab/tests/evaluation/test_observations.py` | `1228e6dbebeb01d13a39a910d954aefe464a9744f4d9fe82ce5ba237671158ee` |
| `tools/authorization-lab/tests/evaluation/test_case_manifest.py` | `be03ad6c3a672c1c606067c67d6a0942870598b39f77db54854116c14368c5ea` |
| `tools/authorization-lab/src/authz_lab/fixtures/ownership.csv` | `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f` |
| `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` | `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b` |
| `tools/authorization-lab/src/authz_lab/fixtures/manual_sample_cases.json` | `0ece045d34599487bfbac175e49efc3afce8f2beda4f34f67c41d39817af6eca` |

Automation: xác minh 2026-11-15T15:52:21.136Z, bot không có automation/monitor cần dừng.
