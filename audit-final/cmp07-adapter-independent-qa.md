# CMP07-ADAPTER-01 — QA độc lập

@T18 Lead: **PASS regression offline**, chưa nghiệm thu transport/runtime. Tổng thể **PARTIAL**. Kiểm tại 2026-11-16T00:14:44.073286+07:00; HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`, working tree có diff sẵn có được giữ nguyên.

## Inventory và execution

Python 3.14.8, pytest 9.2.0, pytest-asyncio 1.4.1.post1; pytest-subtests package không cài riêng (pytest hiện tại vẫn chạy 392 subtests). CWD repository hiện tại; timestamps UTC+07. Không thấy AGENTS.md tại root và các thư mục cha đã kiểm. Không truy cập lab/context/credential/process runtime; lab image digest và runtime fixture snapshot **UNKNOWN**, không suy từ fixture metadata.

OpenAPI `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json`: SHA-256 `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b`. Ownership `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f`. Fixture bundle metadata `a02f42b62ba6e6efa08cff2701c0fef3b62722770c0fa1bba1573d3a0465ee37`; đây không phải runtime snapshot. **12/12** source hashes trong plan và **5/5** hashes bàn giao adapter khớp. **22/22** evaluation source/test hashes trước–sau khớp.

Đã chạy pytest toàn `tools/authorization-lab/tests/evaluation` với `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=tools/authorization-lab/src`, `.venv/bin/python`, cache tắt, basetemp tạm tự dọn. Dùng nội dung wrapper bàn giao nhưng đổi output thành `cmp07-adapter-independent-verification.json` để giữ nguyên evidence owner, thêm probes dưới cùng guards trước hash sau. **147 tests + 392 subtests PASS**, 1.21s; **4 QA probes PASS**, wrapper exit 0. Warning asyncio fixture scope unset là deprecation, không có test fail. Guards chặn socket connect/connect_ex/sendto/create_connection, DNS và subprocess.Popen/os.system/fork/posix_spawn; đây là guard Python trong process, không phải sandbox OS.

Evidence: [log](cmp07-adapter-independent-regression.log), [hashes trước/sau và probes](cmp07-adapter-independent-verification.json). Không sửa source/tests hoặc chạy lại wrapper theo cách ghi đè evidence owner.

## Review và kết quả

| Hạng mục | Kết quả trong phạm vi offline |
|---|---|
| Scope/dry-plan/mapping | PASS: exact loopback origin/path, frozen digests, verified flag, aliases, case membership, admin/book unresolved reject; dry-plan không I/O. Verified flag là đầu vào chưa attested. |
| Caps/accounting | PASS: total/phase cap trước dispatch; exception vẫn tính; concurrency 1, single-use, retries=0. Cap chỉ đếm transport.get, chưa chứng minh số request HTTP thật. |
| Redirect/body/timeout | PASS fake: 301/302/307 reject trước body; timeout read đóng response; bounded chunk/sentinel, invalid JSON/content type/duplicate keys reject. QA probe 308 reject; 204 empty không CONFIRMED. |
| Cancel/expiry | PASS fake: pre-cancel không dispatch; QA external task.cancel ở read baseline đóng response, dừng tại 3 dispatch; expiry sau GET đầu dừng tại 1. External cancellation re-raise và **không có receipt trả về**. |
| Owner baseline | PASS: identity, object, owner và protected scalar bắt buộc; null/missing/empty/error/non-JSON/wrong identity không confirm. Candidate so exact type/value protected paths. SELF/public/identity không CONFIRMED. |
| Redaction | PASS canary: output không có username/protected value/exception text/body/header; receipt chỉ symbolic metadata. Chưa kiểm client HTTP logging. |
| Schema2/integrity | PASS: receipt payload schema1 được carry trong envelope schema2, SHA-256 + exact case/manifest/execution/status/signal binding; đổi execution rồi recompute envelope digest vẫn reject. Attestation UNVERIFIED, timing null/UNKNOWN. |

Không phát hiện regression fail trong suite đã chạy. Không suy mọi branch đều được test: close/get không hợp tác, crash/persistence, proxy/DNS routing, TLS, socket cancellation thực tế, 3/5 roles, anonymous/invalid-token và authorized-sharing runtime đều **NOT_RUN**. Các cases synthetic dùng `setup()` trong test_bounded_adapter (one book OTHER/DENY, actor a/owner b, fixture c×64/policy v1, execution d×32); không phải 13 cases CMP07 chạy trên lab và không tạo run_id thực nghiệm. CONFIRMED synthetic chỉ kiểm comparator theo policy fixture, không phải truth label lab.

## Ticket tiếp theo và tiêu chí nghiệm thu

**CMP07-TRANSPORT-01 — owner đề xuất OpenAPI Matrix; gate QA độc lập trước CMP07-RUN-01.** Bổ sung transport HTTP thật, giữ nguyên default fail closed. Một dispatch đúng một GET; không retry/redirect/proxy ngoài scope; pin exact approved origin/path và credential principal, không login/discovery. Test HTTP integration bằng server loopback có counter độc lập (ticket cần quyền mở listener/process): tổng/phase cap khớp socket/server count kể cả disconnect; 301/302/303/307/308 không có request thứ hai; 204/401/403/500 và 200 error không tạo false CONFIRMED. Test streaming/chunked/oversize/decompression bound, stalled headers/read/close, timeout/cancel abort socket và không còn task/I/O; không giữ raw response/secret trong logs. Timeout của asyncio phụ thuộc transport hợp tác, không coi wait_for là bằng chứng hard deadline. Không dùng legacy urlopen fallback. Cấp cap tại lớp thật cho ZAP riêng, không dùng history count thay enforcement.

**CMP07-CANCEL-RECEIPT-01 — owner đề xuất adapter/orchestrator.** External cancellation hiện re-raise trước dựng envelope (đã reproduce). Nếu run cần audit terminal cho mọi attempted request, bổ sung persistence accounting/terminal cancelled artifact ở boundary; kiểm task.cancel giữa get/read/close và crash recovery không replay. Đây là gap vận hành đã biết, không phải failure so với contract adapter single-run hiện tại; chưa cho phép tuyên bố cancellation/crash evidence đầy đủ.

**CMP07-WHOLEBODY-01 — owner đề xuất BOLA Evaluator + contract owner.** Hiện chỉ protected paths, thiếu shape/length và normalized whole-body comparison metadata. Định nghĩa normalization/version và explicit dynamic-field policy; giữ id/owner/protected fields, array order và type; ghi lengths/shape/similarity có provenance, không raw body. Whole-body similarity không tự nâng CONFIRMED. Test dynamic timestamps, owner/id mismatch, null/missing, ordered arrays và stable metadata hash; bind case/fixture/policy/execution. Nếu cần HTTP status/conclusion/field paths trong receipt phải mở contract revision, giữ schema2 validation/legacy compatibility. Sidecar digest hiện chỉ được tạo; consumer phải validate nếu dùng sidecar làm evidence quyết định.

**CMP07-RUN-01** còn cần approval target/budget/expiry hiện tại, >=3 verified principals/owner snapshot, policy admin/book và truth review có nguồn, cùng fixture cho manual/T18/ZAP; 5-role là gate riêng. Không reuse approval cũ hoặc Run #2. BFLA/disposable, DB proof và Browser E2E tách biệt, chưa có evidence mới.

## Verdict

Unit/regression **PASS** trong fake transport; HTTP integration **NOT_RUN**; live/runtime/experiment **NOT_RUN**; DB proof **UNKNOWN**; Browser E2E **BLOCKED** theo trạng thái hiện có, không recheck trong lượt này. **PARTIAL** toàn dự án. Không thay production/tests/runtime/lab/Run #2. Đã kiểm: bot không có automation.
