# CMP-04 — deterministic metrics và exports

Ngày 2026-11-15; T18 ZAP Comparison. Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Giữ mọi diff hiện hữu. Đã đọc README root/lab, comparison-audit, comparison-hardening, observations report và source manifest/observations. Không tìm thấy AGENTS.md trong repo và các thư mục cha đã kiểm tra.

**PASS regression triển khai; tổng thể PARTIAL, thực nghiệm NOT_RUN.** Chỉ tạo năm file theo ownership:

- `tools/authorization-lab/src/authz_lab/evaluation/metrics.py`
- `tools/authorization-lab/src/authz_lab/evaluation/exports.py`
- `tools/authorization-lab/tests/evaluation/test_metrics.py`
- `tools/authorization-lab/tests/evaluation/test_exports.py`
- `audit-final/research-workflow-metrics-exports.md`

## Contract tích hợp

`evaluate(observations: ObservationSet, truths, predictions, selections)` trả frozen `MetricsResult`. Các collections đầu vào được snapshot thành frozen records; không giữ mutable caller collections. Không I/O/network/process, không orchestration hoặc đọc lịch sử. Mỗi selection là `Selection(method, execution_id)`; bắt buộc explicit, một execution cho mỗi method, không tự lấy latest. Observations ngoài execution đã chọn không bị gộp; missing case có execution khác bị loại EXECUTION_MISMATCH, không có observation bị loại NOT_RUN. Mỗi selection xuất đúng một row cho từng case trong manifest, không gộp actor/owner cùng path.

`ReviewedTruth(manifest_digest, manifest_version, case_revision, decision, reviewed, review_artifact_ref, review_artifact_hash)` ràng buộc exact cohort/revision và opaque artifact reference/hash. Nhãn vulnerability là POSITIVE/NEGATIVE/UNKNOWN, tách khỏi expected ALLOW/DENY của policy. Thiếu hoặc reviewed=False bị loại UNREVIEWED_TRUTH; UNKNOWN bị loại UNKNOWN_TRUTH. Module không tự review ground truth.

`ValidatedPrediction(observation_digest, decision, baseline_validated, protected_field_validated, policy_eligible, source_validated, validation_artifact_ref, validation_artifact_hash)` bind vào exact observation digest gồm source metadata và revision/execution. Bốn boolean đều phải có và là bool thật; false bị loại bằng reason tương ứng. Đây là assertions của upstream validator cần evidence, không phải module đã tự kiểm baseline/body/artifact. Không suy prediction từ ACCESS_ALLOWED/DENIED, ZAP ILLEGAL/LEGAL hay human_observation_verified. Thiếu prediction/UNKNOWN bị loại UNVALIDATED_PREDICTION/UNKNOWN_PREDICTION.

Observation NOT_RUN/INVALID/UNKNOWN/BLOCKED giữ nguyên exclusion; COMPLETED thiếu provenance là UNVERIFIED_SOURCE. Chỉ observation COMPLETED có provenance, reviewed quyết định ground truth và prediction quyết định đủ bốn gates mới có TP/FP/FN/TN. Duplicate truths, duplicate predictions, duplicate method selection, unknown observation/case, mismatched cohort/revision, malformed enum/hash/opaque refs bị reject. Không nhận raw body/secret/resource ID/path trong contract trường evidence; không dùng free-text notes. Các nhãn symbolic/template kế thừa manifest vẫn cần caller review, vì structural validation không phát hiện secret giả dạng symbolic label.

`MetricsResult.summary()` trả per-method/execution TP/FP/FN/TN, cohort_count, eligible_count, excluded_count và precision/recall/accuracy cùng denominator riêng. Denominator 0 trả None, không NaN/0 giả. Recall chỉ tính trên positives đủ điều kiện, không coi excluded là FN; không tuyên bố coverage chung khi thiếu ground truth. Rows chứa observation/source/review/validation hashes và refs, cell hoặc exclusion_reason. Result constructor kiểm exact row coverage/membership, uniqueness và allowlisted fields trước export. Summary trả detached dictionaries.

Exports trả content thuần, caller tự quyết định lưu:

- `comparison_csv(result)`: từng case/method/execution và cohort/source/review/validation identity/hash, cell/exclusion.
- `comparison_markdown(result)`: cùng case rows và fields như CSV.
- `metrics_csv(result)`: summary từng selection, denominators, nullable ratios và cohort binding.
- `evidence_index(result)`: JSON schema_version=1, cùng case rows và summaries, keys/order deterministic.

CSV dùng csv writer và prefix apostrophe khi text bắt đầu công thức (kể cả whitespace trước =/+/−/@). Markdown escape pipe/backtick/backslash, HTML angle/ampersand và line breaks. Evidence refs chỉ opaque `artifact-` + 32 hex, không arbitrary paths, không mở file. Không export raw operation/resource path hoặc body. Hash chỉ nhận diện nội dung được khai báo: module KHÔNG đọc artifact bytes, kiểm hash thực tế, xác thực reviewer/operator/trust anchor hoặc attestation. Caller không được gắn verified chỉ từ metadata. Contract additive Python, chưa persisted schema/importer/CLI/API/UI integration; không sửa comparison.py/timing.py.

## Fresh regression

Từ root, lệnh cuối:

```sh
PYTHONPATH=tools/authorization-lab/src .venv/bin/python - <<'PY'
from unittest.mock import patch
import pytest
with patch('socket.socket.connect',side_effect=AssertionError('network blocked')), patch('socket.socket.connect_ex',side_effect=AssertionError('network blocked')), patch('socket.create_connection',side_effect=AssertionError('network blocked')), patch('subprocess.Popen',side_effect=AssertionError('process blocked')), patch('os.system',side_effect=AssertionError('process blocked')):
    raise SystemExit(pytest.main(['tools/authorization-lab/tests/evaluation/test_metrics.py','tools/authorization-lab/tests/evaluation/test_exports.py','tools/authorization-lab/tests/evaluation/test_observations.py','tools/authorization-lab/tests/evaluation/test_case_manifest.py','-q','--tb=short','-p','no:cacheprovider']))
PY
```

**31 tests + 259 subtests PASS, exit 0** (0.42s là thời gian chạy unit tests, không benchmark method). Fixture hoàn toàn synthetic, asserted review/validation không phải reviewed ground truth thật. Gồm bốn confusion cells, từng eligibility gate, statuses/execution mismatch/missing source/unknown, human metadata và ZAP signal không tạo prediction, denominator null, duplicates/malformed/mismatches, unsafe export records, deterministic CSV/Markdown/index và escaping. Temp exports trong TemporaryDirectory `cmp04-*`; network/process entry points bị block, không sandbox OS. Warning pytest-asyncio loop scope hiện hữu.

Lượt đầu collection exit 2 do import fixture test chưa dùng package-relative; đã sửa trước các lượt PASS. Lượt kế 29 tests/255 subtests PASS; lượt cuối trên gồm thêm tests result validation/metrics CSV. Không skip/xfail.

`git diff --check`: fresh exit 0. Kiểm whitespace/final newline riêng năm file mới: exit 0. Automation check cuối: bot không có automation cần dừng.

## Dependencies / chưa xác minh

CMP-05: importer/catalog phải verify bytes/hash, reviewed mapping và authorization/project scope; xây trust/attestation provenance cho claims trước khi gọi evaluate. Chưa nối orchestration hoặc legacy history, không linked Run #2.

CMP-06: API/UI đọc comparison, exclusions/evidence index và nullable denominator/timing. Chưa nối web, không import/call lab CLI từ web.

CMP-07: independent QA cho CMP-04, reviewed ground truth thật, manual benchmark cùng cohort, ZAP context/approval/auth/scope/request gates và thực nghiệm 3+ roles. Chưa có ground truth thực đã review; không bịa metrics/timing. Thực nghiệm manual/T18/ZAP NOT_RUN; Browser E2E giữ blocker hiện hữu, không login lại.

Không network/lab/ZAP/lifecycle/runtime/Run #2/DB/deploy/commit/push/reset/xóa evidence. Không sửa files ngoài ownership hoặc ba tài liệu QA.
