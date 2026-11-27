# CMP-02 — canonical comparison case manifest

Ngày 2026-11-15, T18 ZAP Comparison. Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Đã đọc README root/lab, comparison audit, comparison hardening và compare implementation. Không tìm thấy AGENTS.md trong repo và các thư mục cha đã kiểm tra. Giữ mọi diff có trước; hai file source/test mới chưa tồn tại trước ticket.

**PASS regression CMP-02; tổng thể PARTIAL.** Chỉ tạo module `tools/authorization-lab/src/authz_lab/evaluation/case_manifest.py`, regression `tools/authorization-lab/tests/evaluation/test_case_manifest.py` và báo cáo này. Không sửa comparison/timing, backend/frontend/schema hoặc tài liệu trạng thái QA.

## Contract downstream

Module thuần Python standard library, không I/O, không tự tạo artifact hay gọi runner. Dùng chung một manifest cho MANUAL/T18/ZAP; method identity không nằm trong case ID nên ba phương pháp join cùng case. Manifest không mang observations, timing, execution status hoặc ground-truth approval.

- `CaseDefinition(...)`: frozen/slotted, chỉ các trường scalar. Bắt buộc method uppercase GET/HEAD/OPTIONS/POST/PUT/PATCH/DELETE; operation_template là path OpenAPI chưa render (có thể `/`), không URL/query/fragment/percent encoding, segment rỗng hoặc dot traversal. Chấp nhận template metadata write không cấp phép thực thi write.
- `actor_alias`: `actor-` + 32 lowercase hexadecimal characters; `owner_alias`: `owner-` + 32 lowercase hexadecimal characters cho SELF/OTHER. Alias phải opaque, được cấp và giữ ổn định upstream; không dùng username/resource ID hay hash trực tiếp bí mật làm alias. PUBLIC/NONE bắt buộc owner_alias=null. SELF/OTHER/PUBLIC/NONE là quan hệ sở hữu, không suy từ alias khác namespace.
- `actor_role`, `policy_id`: ASCII symbolic label bắt đầu bằng chữ, tối đa 64 ký tự, chỉ letters/digits/underscore/hyphen. Role là vocabulary lab do caller chỉ định, không hardcode role người dùng hay web role.
- `fixture_version`, `policy_version`: nhãn version bắt đầu alphanumeric, tối đa 64, cho phép letters/digits/underscore/dot/hyphen; ví dụ `1`, `v1`, `1.2.3`. `fixture_hash`: SHA-256 lowercase hex 64 ký tự của fixture đã review/redact upstream; không hash raw sensitive response làm chứng cứ mặc định. `expected_decision`: exact ALLOW/DENY, caller phải cung cấp; không có default hay suy đoán policy.
- `case.case_id`: `case-` + SHA-256 canonical JSON toàn bộ trường ngữ nghĩa. ID opaque và ổn định khi nội dung không đổi; bất kỳ trường nào đổi tạo ID mới có chủ ý. Đây là identity của một revision, không ID cố định xuyên revision. Không chứa raw alias/role/resource value trong ID.
- `CaseManifest.build(iterable_of_cases)`: snapshot tuple bất biến, sort theo case_id. Từ chối empty, duplicate ID và duplicate scenario (method/template/actor alias/role/owner alias/category), kể cả khi policy/fixture/expected khác nhau. Không cho hai revision cùng scenario trong cùng cohort.
- `content_digest`: SHA-256 JSON `{schema_version: 1, cases: sorted_case_dicts}`; `version`: `sha256:<content_digest>`. Canonical encoding `sort_keys=True`, compact separators, ASCII JSON, UTF-8/ASCII bytes, không timestamp/path/runtime metadata. Đổi role/owner/policy/fixture hoặc membership đổi cohort version; reorder đầu vào giữ nguyên. `schema_version` là version format, tách với content version.
- `to_dict()`: detached JSON-compatible copy, không mutable reference vào manifest. `CaseDefinition.from_dict` và `CaseManifest.from_dict` require exact fields, reject missing/unknown fields, invalid enums/types, unknown schema (kể cả bool), digest/version mismatch. Có thể serialize bằng json ở caller được giao importer.
- `require_case(case_id)`: exact membership lookup, unknown/legacy ID raise ValueError; không fallback path/actor matching. Caller phải kiểm tra manifest version/digest trước lookup và không tự nối cohort khác.

Ví dụ sử dụng (tất cả synthetic):

```python
from authz_lab.evaluation.case_manifest import CaseDefinition, CaseManifest
case = CaseDefinition(
    method='GET', operation_template='/users/v1/{username}',
    actor_alias='actor-' + 'a' * 32, actor_role='userA',
    owner_alias='owner-' + 'b' * 32, owner_category='OTHER',
    fixture_version='v1', fixture_hash='c' * 64,
    policy_id='cross_user', policy_version='v1', expected_decision='DENY',
)
cohort = CaseManifest.build([case])
restored = CaseManifest.from_dict(cohort.to_dict())
assert restored.require_case(case.case_id) == case
```

Validation là cấu trúc, không thể biết một chữ trong static path/role có phải tên thật hay bí mật. Caller phải lấy operation template từ inventory được review, không truyền literal username hoặc resource ID trong static segment; module không đọc spec, fixture bytes hay credential để xác minh. Alias format không chứng thực nguồn alias. Hash chỉ bảo vệ content identity/accidental mismatch, không chữ ký hoặc approval. Manifest bất biến trong sử dụng Python thông thường; không là sandbox chống caller chủ động bypass dataclass.

## Fresh verification

Từ root, lệnh cuối:

```sh
PYTHONPATH=tools/authorization-lab/src .venv/bin/python - <<'PY'
from unittest.mock import patch
import pytest
with patch('socket.socket.connect', side_effect=AssertionError('network blocked')), patch('socket.socket.connect_ex', side_effect=AssertionError('network blocked')), patch('socket.create_connection', side_effect=AssertionError('network blocked')), patch('subprocess.Popen', side_effect=AssertionError('process blocked')), patch('os.system', side_effect=AssertionError('process blocked')):
    raise SystemExit(pytest.main(['tools/authorization-lab/tests/evaluation/test_case_manifest.py', '-q', '--tb=short', '-p', 'no:cacheprovider']))
PY
```

**10 passed, 89 subtests passed in 0.08s; exit 0.** Test artifact chỉ trong TemporaryDirectory `cmp02-*`, fixture hoàn toàn synthetic. Bao phủ roundtrip JSON, order independence, mọi semantic field đổi digest/version, golden SHA-256 vector, duplicates/conflicting scenarios, unknown case, missing/unknown/tampered fields, malformed values/path, frozen objects/detached export, null-owner categories và version labels. Không skip/xfail. Lượt trước 8 tests/85 subtests PASS; sau đó thêm golden vector và numeric/semver versions. Warning pytest-asyncio loop scope hiện có. Không chạy full web/lab suite.

`git diff --check`: exit 0. Ba lệnh `git diff --no-index --check /dev/null <file>` cho ba file mới đều không output, exit 1 (no-index báo có khác biệt với /dev/null). Kiểm tra bổ sung bằng Python cho ba file: không trailing whitespace, không space-before-tab, có final newline; exit 0. Automation check: bot không có automation.

## Compatibility và dependencies chưa triển khai

API additive, chưa được import/call bởi orchestration/comparison/web. Không đổi output cũ, không migrate lịch sử. Legacy case IDs (M-01, resource-derived IDs, web persisted keys) không tự tương thích; cần mapping explicit được review. Không khẳng định manifest này liên kết Run #2 hoặc cohort lịch sử. Không tạo ground truth đã duyệt và không tính metrics/coverage thực nghiệm.

CMP-03: adapters/provenance và mapping manual/T18/ZAP, role registry/alias allocation, source hashes và validation same-cohort còn thiếu. CMP-04: ground-truth review, TP/FP/FN/TN denominators và CSV/MD/evidence index chưa triển khai trong ticket này. CMP-05: importer/store/API scoped và kiểm chứng digest/provenance chưa nối manifest này. CMP-06: UI case alignment theo manifest chưa nối; UI Compare hiện hữu không đồng nghĩa integration CMP-02. CMP-07: nghiệm thu manual/ZAP cùng cohort, timing benchmark và 3/5-role lab chưa thực hiện. Thiếu observations giữ NOT_RUN/UNAVAILABLE ở downstream, không dựng counts=0 hay COMPLETED từ manifest.

Không network/lab/ZAP/BFLA/lifecycle/CLI orchestration/runtime DB/deploy/commit/push/reset/xóa hoặc sửa results lịch sử; Run #2 giữ nguyên. Bàn giao Lead/QA review độc lập; kết quả ở đây chỉ là regression module synthetic.
