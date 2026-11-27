# AUDIT-02 — Owner baseline, classifications và evidence UI

Ngày: 2026-11-13. Audit tĩnh tại HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`.
Phạm vi: production code read-only; chỉ tạo báo cáo này. Không chạy lab, request HTTP, browser, tests, commit/push/reset. Không tìm thấy AGENTS.md áp dụng trong repo/các thư mục cha đã kiểm tra.
Working tree lúc bắt đầu: untracked `T18-context-snapshot.zip`, `context-snapshot/`, `audit-final/`; giữ nguyên các nội dung cũ.
Nguồn yêu cầu: kế hoạch `/home/cuong/.openmausbot/attachments/7360d4f9-3db2-460c-8322-b6e100f83310.md`, ticket AUDIT-02.

## Kết luận

PARTIAL cho readiness evidence demo. Ba engine có semantics khác nhau; không được đổi tên verdict để coi chúng tương đương. Các phát hiện dưới đây là suy luận trực tiếp từ code, chưa phải reproduction runtime.

## Semantics và divergence có vị trí

| Vùng | Hành vi hiện tại và ý nghĩa |
|---|---|
| Web owner validity | `backend/app/workers/runner.py:32` xác minh principal qua completed response, 2xx và pointer/expected. Owner baseline ở `:183` và batch `:246` chỉ cần owner principal đúng, JSON tồn tại, resource pointer bằng external ID (`:185`, `:247`). **Không kiểm tra baseline status/execution/truncation/parse flags, ownership field hoặc restricted values đầy đủ/nonempty.** Vì vậy không tương đương owner read thành công. |
| Web evaluator | `backend/app/scanner/classification/evaluator.py:40` ưu tiên conflict/no-rule, sau đó transport/JSON, rồi principal/owner invalid (`:52`). DENY + resource ID đúng + tất cả restricted pointers bằng owner xác nhận violation (`:60–68`); status 403 vẫn có thể leak. Equality dùng Python recursive equality, không normalization, không similarity threshold. `null == null` hoặc empty values vẫn match; cần ca chống false positive. |
| Web ALLOW/UNKNOWN | `evaluator.py:81–83` kết luận POLICY_CONSISTENT_CASE khi resource đúng cho mọi decision không phải DENY. Enum có UNKNOWN (`backend/app/domain/contracts.py:29–32`); resolver có thể trả RESOLVED cho UNKNOWN (`classification/policy.py:78–84`). Do đó UNKNOWN có thể rơi vào nhánh như ALLOW: P0 cần explicit insufficient-evidence gate, không hiển thị PASS. |
| Web denial | `evaluator.py:69–80`: denial convention được hỗ trợ khi truyền vào, nhưng runner `:192`, `:254` không truyền convention. HTTP 401/403/404 thông thường không tự thành PASS; JSON vắng thành NOT_EVALUATED, JSON không có resource thành INSUFFICIENT_EVIDENCE. Không được coi mọi non-200 là denied PASS. |
| CLI comparator | `tools/authorization-lab/src/authz_lab/read_only/response_comparator.py:106–109`: owner CONTROL_PASS chỉ theo 2xx. `:178–191` chọn baseline theo operation/resource, không kiểm tra baseline valid/status/principal. `:128–136` xác nhận cross_user BOLA khi 2xx và ít nhất một sensitive path match; không kiểm tra response resource ID/owner, explicit policy hoặc allowed sharing. Sai resource hoặc baseline lỗi có thể vẫn match. |
| CLI equality | Comparator `:9–23` bỏ timestamp/request_id/created_at/updated_at đệ quy; `:40–48` tính Jaccard leaf path/value, chỉ làm summary; `:51–59` sensitive equality theo path, tên secret/password/token/auth_token. Một giá trị null/empty trùng cũng có thể match; baseline.get(path) trả None khi path vắng có thể match null của actor. List giữ thứ tự; không coi similarity=1 là proof. |
| CLI status denial | Comparator `:112–114` coi 401/403/404 DENIED trước xét body; khác web và có thể bỏ sót body leak. Public read trả OBSERVATION trước control/status (`:99–104`). |
| CLI independent verifier | `tools/authorization-lab/src/authz_lab/verification/manual_verifier.py:91–100`: baseline phải HTTP 200, dict, book_title/owner khớp fixture và secret chuỗi nonempty. `:170–188`: actor 200, đúng title/owner và secret mới lấy từ owner; user→user/user→admin CONFIRMED, mọi actor admin có match thành POLICY_DEPENDENT_ADMIN_ACCESS. Không principal verification, không policy/version explicit, không authorized-sharing PASS. |
| Independent negative | `manual_verifier.py:188` gom không match, baseline lỗi, network lỗi, denied vào NOT_REPRODUCED. UI phải giữ owner_baseline_valid/status/error (`:198–205`), không suy ra PASS từ NOT_REPRODUCED. Không có owner-control record riêng trong records (`:165–167`). |

Web CONFIRMED_VIOLATION là vi phạm rule DENY, không tự phân biệt BOLA/BFLA theo tên enum. Tuyến GET object/resource này nên được mô tả là object authorization khi có fixture ownership; debug credential exposure phải giữ category riêng.

## Evidence UI: có gì thực sự, được phép hiển thị gì

- `backend/app/api/workflow_routes.py:503–517`: results có case_key, execution_status, authorization_conclusion, reason_codes, http_status, response_metadata. Runner `:193`, `:255` chỉ ghi metadata body_length/body_truncated/json_parse_error; không có raw body trong result. UI hiện chỉ case/execution/conclusion/HTTP (`frontend/src/App.tsx:173`); có thể thêm reason codes và metadata số/bool đã allowlist.
- `workflow_routes.py:520–534`: findings có id/fingerprint/conclusion, operation method/path, policy id/version, reproduction_count. Đây là aggregate theo project; `frontend/src/App.tsx:171` tải findings toàn project khi chọn run. Không được gắn nhãn là findings của run đang chọn.
- `backend/app/services/findings.py:45–69` fingerprint theo policy/version/mapping và `:79–84` liên kết reproduction→run_result/actor/resource trong DB. API hiện không trả reproduction/run/case link. Cần endpoint đọc có schema allowlist hoặc mở rộng contract theo ticket riêng; frontend không tự suy luận liên kết từ count.
- **Thiếu persisted evidence**: owner_control_valid, owner status/execution, principal-valid flags, restricted match summary, baseline reference, policy resolution/version cho từng case và artifact reference. Không suy owner-valid=true chỉ từ CONFIRMED hoặc metadata. `run_id` hiện lấy từ request context; dùng cặp run_id + case_key làm trace UI, giữ raw key để không phát minh case_id.
- Có thể bổ sung sau khi thực sự persist: source engine/version, run/case/fixture alias, policy id/version/decision/resolution, owner status và validity/reason, matched pointer names + booleans, body length/truncated/parse flags, artifact public ID/hash. Pointer/path/alias vẫn cần kiểm tra không chứa secret hoặc ID nhạy cảm do người dùng đưa vào; không hiển thị arbitrary metadata bằng JSON dump.
- Không đưa token/password/secret value, raw response/text, auth headers, principal giá trị nhạy cảm, absolute artifact paths lên UI/export. Independent verifier records giữ match boolean và shape thay raw body (`manual_verifier.py:190–206`), nhưng error/field names vẫn cần schema/sanitization khi import.
- **Không import thẳng CLI JSON**: request runner chỉ sanitize debug endpoint (`tools/authorization-lab/src/authz_lab/read_only/request_runner.py:59–88`); response_json/response_text của book còn được giữ. Pipeline ghi raw_results/final_report (`read_only/pipeline.py:64–65`). `common.py:25–32` chỉ từ chối token-like regex, không phải redactor tổng quát cho secret/password. Comparator cũng copy dict raw (`response_comparator.py:90`). Nhãn “redacted artifact” không đủ chứng minh an toàn.

## Acceptance cases đề xuất (chưa chạy)

Mỗi ca phải có run_id, case_id hoặc case_key, fixture ID/owner evidence, engine/version, policy/version và artifact đã sanitize. Không dùng dữ liệu thật. QA lưu expected và actual riêng.

| Case ID | Fixture/trigger | Expected nghiệm thu và khác biệt cần ghi |
|---|---|---|
| OC-01 | Owner principal đúng; baseline completed 200, ID/owner đúng, nonempty secret; explicit ALLOW | Owner PASS có bằng chứng baseline; web POLICY_CONSISTENT_CASE, comparator CONTROL_PASS; independent verifier cần adapter baseline summary riêng. |
| BOLA-01 | User B đọc resource A, explicit DENY, đúng ID/owner và nonempty nested secret bằng fresh owner | Web CONFIRMED_VIOLATION; comparator CONFIRMED; independent USER_TO_USER khi fixture book phù hợp. Chỉ công bố CONFIRMED sau đủ provenance. |
| SHARE-01 | Cùng response như BOLA-01 nhưng policy ALLOW sharing | PASS authorized sharing ở web. Comparator hiện có thể CONFIRMED và independent vẫn user-BOLA; comparison phải đánh dấu policy divergence, không majority vote. |
| ADM-01 | Admin đọc user resource, chưa có policy quyết định | Independent POLICY_DEPENDENT_ADMIN_ACCESS; web no-rule INSUFFICIENT_EVIDENCE. Explicit ALLOW→PASS, explicit DENY + evidence→violation; không gộp ba trạng thái. |
| NEG-01 | HTTP 200 chỉ có public fields hoặc generic error | Không CONFIRMED; web insufficient, CLI inconclusive; HTTP 200 không đủ. |
| NEG-02 | Response sai resource ID nhưng secret trùng | Không CONFIRMED theo acceptance; web chặn, comparator hiện có thể xác nhận sai. |
| NEG-03 | Baseline 403/500 có ID/secret trùng actor; hoặc thiếu owner/empty/null secret | Owner invalid/inconclusive, không CONFIRMED; web/comparator có khoảng trống đã nêu; verifier strict chặn. |
| NEG-04 | Actor principal mismatch hoặc token của owner dùng nhầm cho actor | INVALID_TEST; CLI không có principal gate tương đương, không báo trusted confirmed từ fixture role label. |
| NEG-05 | Policy UNKNOWN/no match/conflict | Không PASS/CONFIRMED; lần lượt insufficient/insufficient/blocked. UNKNOWN hiện có fallthrough cần sửa. |
| DENY-01 | 403 không leak, resource ẩn | Không BOLA; giữ raw verdict; web chưa có supported-denial evidence thì inconclusive/not evaluated, CLI DENIED. Không ép parity. |
| LEAK-403 | 403 nhưng body có đúng resource + restricted owner data | Web vẫn CONFIRMED (có unit test `backend/tests/test_evaluator.py:27`); CLI hiện DENIED, verifier NOT_REPRODUCED: divergence cần hiển thị. |
| INC-01 | Timeout/network/parse lỗi/truncated/cancelled hoặc baseline không có | Không PASS/CONFIRMED; giữ execution reason và evidence validity. Independent NOT_REPRODUCED không đủ để nói an toàn. |
| NORM-01 | Nested objects khác thứ tự key và chỉ dynamic timestamps đổi | Comparator similarity có thể 1; web restricted pointer trên whole object có thể khác; quyết định theo configured restricted values và policy, không similarity đơn độc. |
| REDACT-01 | Synthetic canary secret/password và token-like strings trong body/error/field names | UI/export/log không chứa giá trị canary; chỉ matched booleans/pointer names đã kiểm tra. Kiểm tra raw CLI JSON không đi xuyên qua adapter. |
| TRACE-01 | Hai runs cùng fingerprint, nhiều reproduction | Findings tổng project phải ghi phạm vi; drilldown đúng run/case/policy version/owner evidence/artifact; count không được giả làm kết quả run. |

## Ticket/ownership đề xuất

1. P0 evaluator owner: harden owner baseline validity; chặn UNKNOWN; định nghĩa nonempty restricted evidence và kiểm thử null/missing. Không sửa chỉ để ép parity CLI.
2. P0 evidence persistence/API: lưu summary owner/comparison và case-policy provenance tại execution, expose read-only allowlist; cần Lead giao file lock runner/services/routes để tránh AUDIT-01 chồng việc.
3. P0 frontend Lead: giữ source verdict + display label, reason code, execution và validity riêng; run-scoped reproduction link; không chuyển NOT_REPRODUCED thành PASS.
4. P1 CLI owner: invalid-baseline/resource/policy guards và structured negative outcomes; import adapter phải sanitize trước browser API, không đưa CLI execution vào web.
5. QA owner: thực thi các acceptance cases trên pure synthetic/unit fixtures trước; lab/browser E2E chỉ trong đợt đã được giao riêng.

## Verification status

- PASS: xác minh HEAD, đọc code/contracts/tests và truy vết path/line nêu trên.
- PARTIAL: semantics và evidence contract đã audit tĩnh; các lỗ hổng guard là nhận định từ nhánh code, chưa chạy reproduction.
- NOT_RUN: unit tests, lab/runtime/browser, E2E, security/redaction canary execution.
- Không có automation của bot cần dừng (đã kiểm tra).
