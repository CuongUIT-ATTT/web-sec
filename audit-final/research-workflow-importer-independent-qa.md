# CMP05-A — QA độc lập pure comparison importer

**PASS independent focused regression; tổng thể PARTIAL.**

Run ID QA-CMP05A-20261115-230352. Timestamp 2026-11-15T23:03:52.336691+07:00, Asia/Ho_Chi_Minh (UTC+07). Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd` xác minh trước/sau. Giữ mọi diff có sẵn. Python 3.14.8, pytest 9.2.0 từ `.venv`; không cài dependency. Đã đọc root/lab README, báo cáo comparison-importer, source importer và contracts case_manifest/observations/metrics/exports cùng importer tests. Không tìm thấy AGENTS.md trong repository/các thư mục cha đã kiểm tra (rg không match exit 1, không phải test failure).

Lab digest/attestation **NOT_VERIFIED**, không truy cập lab. OpenAPI và fixture hash dưới đây là fixture đóng gói; toàn bộ case/policy/receipt regression synthetic, không phải benchmark hay thực nghiệm 3+ roles.

## Fresh commands và exits

Từ root: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/authorization-lab/src .venv/bin/python -` với wrapper hash trước/sau. Mỗi suite chạy riêng:

```python
pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp', tmp+'/'+name,
             'tools/authorization-lab/tests/evaluation/test_'+name+'.py'])
```

TemporaryDirectory prefix `qa-cmp05a-`; TMPDIR và tempfile.tempdir vào temp riêng. ExitStack/unittest.mock.patch chặn socket.socket.connect/connect_ex/sendto, socket.create_connection/getaddrinfo/gethostbyname/gethostbyname_ex, subprocess.Popen, os.system/posix_spawn/posix_spawnp/fork bằng AssertionError. Đây là guards trong process, không phải OS sandbox. Không chạy disposable suite.

| Suite | Tests | Subtests | Fresh exit |
|---|---:|---:|---:|
| importer | 8 | 67 | 0 |
| case_manifest | 10 | 89 | 0 |
| observations | 11 | 87 | 0 |
| metrics | 6 | 35 | 0 |
| exports | 4 | 48 | 0 |
| Tổng | 39 | 326 | 0 |

Wrapper exit **0**, 13/13 hashes trước/sau khớp. Không failure/skip/xfail được báo; pytest-asyncio warning về unset loop scope hiện có. `git diff --check` sau cập nhật docs: exit **0**. Record máy đọc: `.qa-cmp05a-result.json` cùng thư mục (exits và cả hai hash maps); không chứa secrets hay raw responses.

## Review và giới hạn

- Exact manifest digest/version, membership/case revision được xác minh lại bằng CaseManifest; observations bind exact cohort và revision. Duplicate method/execution/case bị reject; selection là explicit một execution/method, không suy latest. Selection không có observations được giữ để downstream báo NOT_RUN/execution mismatch, không coi là bằng chứng execution đã xảy ra.
- Catalog phải đúng tập artifact referenced; SHA-256 tính trực tiếp từ exact bytes, kể cả whitespace. Receipt allowlist phải khớp exact manifest/case/method/execution/status/signal; hash đúng nhưng nội dung sai binding vẫn reject. Không mở paths, đọc history, gọi network/process hoặc tạo approval.
- Malformed UTF-8/JSON, duplicate JSON keys, schema/type/version, missing/unknown/duplicate, tampered hash/revision/execution, size/depth/count/string/integer limits và secret/body/resource/path/review canaries đã có synthetic assertions. Artifact/total cap tests dùng patched limits; không phải stress/load benchmark.
- Output detached deterministic JSON, sorted selection/inventory/catalog; catalog và global attestation_status giữ UNVERIFIED. Hash match chỉ integrity của bytes caller cấp, không source authentication, human attestation hay ground truth. Import không nhận truths/predictions; downstream metrics vẫn excluded UNREVIEWED_TRUTH nếu chưa review riêng. human_observation_verified metadata không được nâng thành xác nhận thực nghiệm.
- Legacy giữ UNLINKED/UNKNOWN, không đoán cohort/case. Legacy không provenance đã test trực tiếp; nhánh legacy receipt có provenance được review source nhưng chưa có positive test riêng trong suite hiện tại. Structural allowlist không nhận diện được secret/raw ID giả dạng label/template hợp lệ; cần upstream review/redaction. Không chứng thực fixture_hash của manifest bằng fixture bytes: đó vẫn là contract upstream, khác receipt hash importer thực tính.
- Pure importer đạt regression trong phạm vi này. Chưa kiểm backend authorization, API/store/persistence, frontend, orchestration hoặc historical mapping. Web không được import/call CLI; tích hợp serialized DTO vẫn pending.

CMP05 API/store, CMP06/UI và CMP07 **chưa nối/chưa nghiệm thu**. BFLA04 owner đang triển khai ngoài phạm vi. Manual/ZAP/BFLA thực nghiệm và 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED**, không login lại. Không sửa production/tests; không lab/network/runtime/DB/Run #2/Docker/browser/deploy/commit/push/reset hoặc xóa evidence.

Automation kiểm trực tiếp 2026-11-15T16:04:03.980Z: bot không có automation/monitor cần dừng.

## SHA-256 trước = sau (13 artifacts)

| Artifact | SHA-256 |
|---|---|
| `tools/authorization-lab/src/authz_lab/evaluation/importer.py` | `e3a3b34aaf6c4dce468d43a699b4a8ca3614fc735125cc2efa9c26e89a34eb97` |
| `tools/authorization-lab/src/authz_lab/evaluation/case_manifest.py` | `38fb21fecc9b6a40dbc558a38b0f9e99956e76dfc1701903de0d638b9d8f9fb3` |
| `tools/authorization-lab/src/authz_lab/evaluation/observations.py` | `72cda5b6d69603672392ef913382e3920ddf7213d5fb9f9432263f17823bcf69` |
| `tools/authorization-lab/src/authz_lab/evaluation/metrics.py` | `8993b5d23ed004f60ceea8807d744adb6cf32cc273a4cc31af785d7f5b687642` |
| `tools/authorization-lab/src/authz_lab/evaluation/exports.py` | `ec4b03631399a6db3810e0261eb0c51a806cbaf5e04c0480ea313f1cf9145b1b` |
| `tools/authorization-lab/tests/evaluation/test_importer.py` | `49d5a4c8fc1f47ed48c7edc8949dcd05dfd177809d53285cfa87945a0720f3d4` |
| `tools/authorization-lab/tests/evaluation/test_case_manifest.py` | `be03ad6c3a672c1c606067c67d6a0942870598b39f77db54854116c14368c5ea` |
| `tools/authorization-lab/tests/evaluation/test_observations.py` | `1228e6dbebeb01d13a39a910d954aefe464a9744f4d9fe82ce5ba237671158ee` |
| `tools/authorization-lab/tests/evaluation/test_metrics.py` | `4b4a7d4c1cb56eb374c35be5ef1ccd53ee99d9a7bac8121740f1976c1e12b58b` |
| `tools/authorization-lab/tests/evaluation/test_exports.py` | `1d09b1710d8d9007bdbc1b5a6f58382b041d6931a615d06eef38f6e66a0cc795` |
| `tools/authorization-lab/src/authz_lab/fixtures/ownership.csv` | `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f` |
| `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` | `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b` |
| `tools/authorization-lab/src/authz_lab/fixtures/manual_sample_cases.json` | `0ece045d34599487bfbac175e49efc3afce8f2beda4f34f67c41d39817af6eca` |
