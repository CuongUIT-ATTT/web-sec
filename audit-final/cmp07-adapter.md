# CMP07-ADAPTER-01 — bàn giao triển khai offline

@T18 Lead: adapter và regression offline đã triển khai; chờ QA độc lập. Thực nghiệm NOT_RUN, tổng thể PARTIAL. Không phải approval chạy lab.

HEAD kiểm trước triển khai: bdbba9933ca057cb2247c3a1de9b3ee239c452bd. Đã kiểm AGENTS.md trong repository và các thư mục cha đến /; không có. Đã đọc README root/lab, cmp07-review.md, frozen cohort và contracts case_manifest/observations/importer cùng receipt schema 2. Giữ mọi diff sẵn có.

## File ownership

Chỉ tạo các file thuộc ticket:

- tools/authorization-lab/src/authz_lab/evaluation/bounded_adapter.py
- tools/authorization-lab/tests/evaluation/test_bounded_adapter.py
- audit-final/cmp07-adapter.md
- audit-final/cmp07-adapter-verify.py
- audit-final/cmp07-adapter-verification.json
- audit-final/cmp07-adapter-sha256.txt

Không sửa runner/comparator legacy, importer, backend, frontend hoặc tài liệu owner khác. Không commit/push/reset, login, request lab, start/seed, đọc credentials, tác động runtime/Run #2.

## Contract triển khai

`Principal`, `Mapping`, `Approval` là dataclasses frozen. `BoundedAdapter` kiểm exact membership case/revision qua manifest; approval pin cohort digest, mapping digest, principal context digest, execution và source hash. Mapping explicit actor→principal/role; cùng role phải cùng principal, alias nhất quán. Owner aliases pin cùng resource/fixture/owner mapping. Reject duplicate/missing/unknown cases, changed digest, unresolved admin/book và template chưa review. Không tự nạp historical observations.

Origin chỉ loopback/localhost; URL được ghép từ exact origin và exact path allowlist, reject userinfo/query/fragment/encoding/traversal/foreign URL. Path grammar chỉ /me và book/profile item; không /, login, createdb, debug hay preflight cũ. Allowlist thực tế CMP07 phải pin năm paths trong approval; adapter cũng hỗ trợ cohort synthetic nhỏ hơn để test. Không xác nhận target lịch sử 100.106.64.21:5003. Muốn target ngoài loopback cần ticket/review riêng, không tự nới scope.

`dry_plan()` không I/O, xuất sequence GET identity→owner baselines→cases, tổng/cap từng phase và fits; concurrency=1, retries=0. Không reuse baseline: mỗi case có baseline riêng và tính budget đầy đủ. `run()` single use, đếm trước dispatch kể cả exception. Dừng trước request vượt total/phase cap; cancellation/expiry kiểm trước mỗi dispatch và cancellation kiểm sau read. Async timeout bao cả dispatch/read/close. Read từng chunk <=4096 và tổng <=body_limit+1 (byte sentinel để phát hiện vượt cap); không lưu response body sau khi trả kết quả. Reject mọi non-2xx, redirect trước đọc body, non-JSON, duplicate keys, malformed/truncated JSON, top-level error/message.

Identity response phải khớp username/role của principal verified. Baseline phải cùng request mapping và execution, identity owner hợp lệ, object id/owner khớp và mọi protected path là scalar có giá trị, không null/missing/empty/container. Candidate DENY chỉ CONFIRMED nếu baseline hợp lệ và object/owner/nested protected values khớp exact type/value. Không bỏ owner/id/secret; không sort arrays. Public ALLOW, /me và SELF không sinh CONFIRMED. Generic errors không sinh CONFIRMED. Không suy TN/PASS từ thiếu disclosure; giữ INCONCLUSIVE. Chính sách này cố ý bảo thủ: response 403 và non-2xx giữ INVALID, chưa xác nhận negative access.

Receipt chỉ symbolic metadata; không raw body/header/URL/username/protected value/exception text. Tạo Observation T18 + Provenance và gọi importer schema 2: receipt bytes hash, case_id (bao fixture/policy revision), manifest digest/version, execution/status/signal exact binding. Sidecar có source/mapping/principal digests, source hash, envelope và digest toàn kết quả. Sidecar conclusion là kết quả adapter, không được tự coi là ground truth hay thêm vào receipt schema. Thiếu timing: null/UNKNOWN. Invalid: schema status INVALID + reason INVALID_TEST; chưa dispatch: NOT_RUN với reason; không tự tạo timing 0. Attestation vẫn UNVERIFIED.

## Dependency và giới hạn phải QA xác minh

Không có default transport hoặc CLI wiring. Transport do operator ticket sau cung cấp phải thực sự dispatch đúng một GET, không redirect/retry, async read(n) tuân thủ bound, close/cancellation abort I/O. Flags adapter và fake tests chưa chứng minh một thư viện HTTP thật tuân thủ contract; transport không hợp tác có thể phá timeout/cancel. Không được dùng runner urlopen legacy làm fallback. Hard cap tại adapter áp dụng số dispatch gọi transport; transport thật cần QA độc lập trước CMP07-RUN-01.

Verified principal/fixture snapshot, approval provenance và source hash là input được pin, không phải attestation adapter tự kiểm chứng. Không login/đọc context để tự xác minh. Owner snapshot hiện tại và approval vẫn phải được operator cung cấp. Comparator ở đây kiểm các protected paths explicit; chưa xuất shape/length hay normalized whole-body similarity. Không dùng similarity để suy CONFIRMED. Receipt schema hiện tại không mang conclusion/field path/status HTTP; mở rộng receipt cần owner contract riêng, không sửa chồng trong ticket này. Không có ZAP cap, BFLA/DB proof hoặc Browser E2E trong patch.

## Commands và evidence

Chạy từ repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/authorization-lab/src .venv/bin/python audit-final/cmp07-adapter-verify.py
git diff --check
```

Lần chạy cuối: **147 tests + 392 subtests PASS**, wrapper exit **0**; gồm **49 adapter tests**, toàn bộ evaluation regression. Network/DNS/process guards trong cùng process, không phải sandbox OS. Chặn socket connect/connect_ex/sendto/create_connection, DNS và subprocess.Popen/os.system/fork/posix_spawn. Temp pytest riêng tự dọn, cache/bytecode tắt. Warning pytest-asyncio scope là warning có sẵn. Verification JSON ghi SHA-256 trước/sau của toàn bộ evaluation source/tests; tất cả khớp. git diff --check exit 0 trước bàn giao, chạy lại sau tài liệu.

Coverage synthetic: foreign path/origin/query/fragment, digest/case/principal mismatch, duplicate/missing cases, total/phase cap, failure accounting, cancel/no dispatch, timeout/close, redirect 301/302/307, baseline 401/500, error 200, non-JSON/truncation/duplicate JSON, wrong owner/id/identity, protected null/missing/empty và nested exact match; public/identity không BOLA, unresolved admin reject; canary redaction, schema2 roundtrip và đổi execution/recompute digest vẫn reject receipt.

Không có automation cần dừng (đã kiểm). Bước tiếp theo: QA độc lập adapter và các giới hạn trên; Lead giao transport thật có audit và quyết định các dependency trước thực nghiệm. Không kết luận CMP07 hoàn tất từ fake tests.
