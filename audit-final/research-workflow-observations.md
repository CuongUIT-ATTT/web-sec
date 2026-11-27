# CMP-03 — canonical observations và adapters

Ngày 2026-11-15, T18 ZAP Comparison. Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD đã xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Đã đọc README root/lab, comparison audit/hardening và case-manifest/source/tests. Không thấy AGENTS.md trong repo hoặc các thư mục cha đã kiểm tra. Giữ mọi diff trước ticket; chỉ tạo ba file ownership: `tools/authorization-lab/src/authz_lab/evaluation/observations.py`, `tools/authorization-lab/tests/evaluation/test_observations.py` và báo cáo này.

**CMP-03 PASS regression; tổng thể PARTIAL.** Module thuần, không I/O. Không nối orchestration, không import artifact lịch sử, không sửa comparison/timing, manifest, web/schema, ba tài liệu QA hoặc Run #2.

## Contract tích hợp

- `adapt_manual(manifest, payload)`, `adapt_t18(...)`, `adapt_zap(...)`: exact payload fields là `method`, `manifest_digest`, `manifest_version`, `case_revision`, `execution_id`, `execution_status`, `signal`, `provenance`. Unknown/missing fields bị từ chối. `method` là MANUAL/T18/ZAP, khác HTTP method trong case.
- Exact manifest digest/content version bắt buộc; `case_revision` là toàn bộ `CaseDefinition.to_dict()` của CMP-02, gồm opaque case_id và actor/role/owner/fixture/policy revisions. Adapter revalidate case digest và exact membership, không join bằng path. Thay role/owner/policy/fixture bắt buộc revision/cohort mới. Không chấp nhận legacy M-01 hay đoán mapping.
- `execution_id`: `execution-` + 32 lowercase hex; caller cấp ID ổn định và duy nhất cho một execution, không dùng assessment ID tĩnh hay run number làm fallback. Không tự tạo ID hoặc chứng thực uniqueness toàn hệ thống.
- `provenance`: null nếu thiếu nguồn, hoặc exact object gồm `artifact_ref`, `artifact_hash`, `producer_kind`, `producer_version`, `operator_alias`. Ref là `artifact-` + 32 lowercase hex trong catalog upstream; hash SHA-256 lowercase 64 hex. Không nhận đường dẫn file/URL/traversal. Producer version là symbolic version tối đa 64 ký tự. HUMAN bắt buộc `operator-` + 32 hex; tự động có thể null operator. MANUAL chấp nhận HUMAN hoặc AUTOMATED_VERIFIER nhưng phân biệt hai loại; T18 chỉ AUTOMATED_VERIFIER; ZAP chỉ ZAP. Không nhận body, token, resource IDs hoặc extra fields.
- `provenance_status`: SOURCE_RECORDED chỉ có nghĩa metadata nguồn đầy đủ về cấu trúc, UNVERIFIED khi null. Không có kiểm tra bytes/hash, chữ ký, danh tính hay approval trong module thuần. Importer phải resolve catalog allowlisted, kiểm hash của artifact đã redact và xác minh provenance trước dùng làm bằng chứng thực nghiệm. Alias/format không chứng minh nguồn thực sự là người.
- `human_observation_verified`: chỉ true cho MANUAL + COMPLETED + provenance HUMAN có operator và artifact metadata hợp lệ. Tên property chỉ là gate cấu trúc; **không chứng thực độc lập** artifact, người làm hay ground truth. Automated verifier không bao giờ true, kể cả khi nhập qua manual adapter. Thiếu provenance không true. Upstream cần worksheet/human review thực, không chỉ khai báo producer_kind.
- Status exact COMPLETED/NOT_RUN/INVALID/UNKNOWN/BLOCKED. Các trạng thái ngoài COMPLETED bắt buộc signal UNKNOWN. Signal ACCESS_ALLOWED/ACCESS_DENIED/UNKNOWN; ZAP thêm ILLEGAL/LEGAL. Không nhận BOLA_CONFIRMED, TN/FN/NO_BOLA. ZAP ILLEGAL/LEGAL được giữ nguyên ở signal nhưng conclusion UNKNOWN: không suy protected-field equivalence hoặc xác nhận BOLA từ access-rule.
- `conclusion`: chỉ ACCESS_ALLOWED/ACCESS_DENIED khi COMPLETED, có provenance và signal tương ứng; còn lại UNKNOWN. Access denied là quan sát access, không ground-truth negative/TN. Status thiếu/thất bại không bị chuyển thành negative. Module không tính metrics/timing và không gán elapsed=0; COMPLETED không phụ thuộc stopwatch.
- Frozen/slotted `Observation`, `Provenance`, `ObservationSet`, `LegacyUnlinked`; detached `to_dict()` trên observation, stable canonical SHA-256 `content_digest` dùng encoding của CMP-02. Digest thay khi source hash/metadata thay. Digest là content identity, không attestation. Format hiện tại là additive Python contract, chưa có persisted observation store/migration.
- `ObservationSet.build(manifest, iterable)`: snapshot tuple, revalidate toàn bộ items với cohort, sort theo method/execution_id/case_id. Duplicate cùng triple bị reject kể cả payload mâu thuẫn. Cùng path khác actor/owner là case khác; cùng case khác method hoặc execution được giữ riêng. Nhiều executions không tự gộp: downstream phải chọn execution/cohort trước tính metrics. Empty set hợp lệ là chưa có observation, không tự sinh negatives hoặc counts.
- `LegacyUnlinked(method, source_alias, provenance)`: inventory nguồn lịch sử explicit UNLINKED/UNKNOWN; source alias opaque `source-` + 32 hex, provenance có thể null. Không có case_id, cohort hoặc source_run_id. Không thể đưa vào ObservationSet. Không đọc/resolve nguồn, không tự map lịch sử hay khẳng định linked Run #2.

Operation template/aliases kế thừa giới hạn CMP-02: caller phải lấy template chưa render từ inventory đã review; validation cấu trúc không nhận diện được bí mật giả dạng symbolic metadata hoặc static path. Không gửi thông tin nhạy cảm trong các nhãn cho phép.

## Fresh verification

Từ root:

```sh
PYTHONPATH=tools/authorization-lab/src .venv/bin/python - <<'PY'
from unittest.mock import patch
import pytest
with patch('socket.socket.connect', side_effect=AssertionError('network blocked')), patch('socket.socket.connect_ex', side_effect=AssertionError('network blocked')), patch('socket.create_connection', side_effect=AssertionError('network blocked')), patch('subprocess.Popen', side_effect=AssertionError('process blocked')), patch('os.system', side_effect=AssertionError('process blocked')):
    raise SystemExit(pytest.main(['tools/authorization-lab/tests/evaluation/test_observations.py', 'tools/authorization-lab/tests/evaluation/test_case_manifest.py', '-q', '--tb=short', '-p', 'no:cacheprovider']))
PY
```

**21 tests + 176 subtests PASS; exit 0**, gồm 11 observations tests/87 subtests và 10 manifest tests/89 subtests. Artifacts chỉ trong TemporaryDirectory `cmp03-*`/`cmp02-*`; fixture hoàn toàn synthetic, không ground truth đã review. Network/process thật bị chặn tại các entry points trên; module không chứa network/process/I/O. Đây là guard kiểm thử, không sandbox OS. Warning pytest-asyncio loop scope hiện hữu. Không skip/xfail hoặc failed run trước kết quả này.

Bao phủ ba adapters, roundtrip JSON/deterministic digest, identity khác actor và execution/method, duplicate, cohort/revision mismatch, mọi missing field, malformed enum/type, producer mismatch, incomplete provenance/hash, unsafe refs, unknown sensitive fields, manual automated verifier, ZAP ILLEGAL/LEGAL, noncompleted statuses không negative, immutability/detached exports và legacy unlinked không join được.

`git diff --check`: exit 0. Kiểm tra whitespace/final newline của riêng ba file mới bằng Python: exit 0. Không có automation của bot khi kiểm tra cuối.

## Compatibility và dependencies

API additive, chưa caller nào được thay đổi. Không tự nhận legacy summaries/worksheet/ZAP report cũ là payload canonical; cần importer mapping explicit đã review + catalog nguồn đã kiểm hash. Không rewrite evidence/history. Không khẳng định nguồn synthetic có provenance thực hoặc linked Run #2. Independent QA CMP-03 chưa thực hiện.

CMP-04 còn thiếu: reviewed ground truth, valid execution/baseline/protected-field eligibility, selection execution, TP/FP/FN/TN/exclusion denominator, CSV/Markdown/evidence-index exports. Không dùng ACCESS_ALLOWED/DENIED hay human metadata gate đơn lẻ làm nhãn lỗ hổng.

CMP-05 còn thiếu: importer/catalog kiểm artifact bytes/hash, scope/project/authorization, persisted schema/version và API đọc comparison. Module không được tự import/call CLI từ web; không nối comparison.py hoặc zap runner trong ticket này.

CMP-06 còn thiếu: UI bảng từng case/method từ nguồn thật, badge provenance/linkage và thống nhất status/timing.

CMP-07 còn thiếu: QA review mapping/cohort/ground truth và manual benchmark, controlled ZAP acceptance với toàn bộ context/attestation/auth/scope/request gates, thực nghiệm 3+ roles. Thực nghiệm manual/T18/ZAP **NOT_RUN trong ticket**, không bịa timing/metrics. Browser E2E vẫn theo blocker đã ghi, không yêu cầu đăng nhập lại. Không network/lab/lifecycle/runtime/DB/deploy/commit/push/reset/xóa hoặc sửa results lịch sử.
