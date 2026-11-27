# CMP07-REVIEW-01 — review offline revision 1

@T18 Lead: review tài liệu hoàn thành; execution gate BLOCKED, thực nghiệm NOT_RUN, tổng thể PARTIAL. Không cấp approval chạy lab. HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd. Chỉ tạo cmp07-review*. Không request/login/start/recover, không đọc credentials/context, không tác động runtime/Run #2. Đây là review của BOLA Evaluator; QA độc lập còn thiếu.

## Quyết định có nguồn

Nguồn chính: cmp07-plan-manifest.json, cmp07-plan-cohort.json, cmp07-plan-truth.csv, cmp07-plan-5roles.csv; allowlist-v2.json /allowed_requests; ownership.csv; manual_sample_cases.json; vampi_spec.json /paths. Hash từng nguồn trong cmp07-review-verification.json. Worksheet đi kèm chứa đủ 15 ô, 13 canonical IDs và mapping alias/baseline từng ô. Không chỉnh cohort hoặc policy nguồn.

1. Bốn ô book userA/userB: chấp nhận tĩnh SELF→ALLOW, OTHER→DENY theo allowlist và ownership. Hai owner baseline lần lượt là owner userA/bookA và userB/bookB cùng fixture; metadata ownership không chứng minh runtime baseline hợp lệ.
2. Hai ô admin/book: giữ policy-dependent, không canonical ID, không prediction/truth nhị phân. Chỉ nhãn POLICY_DEPENDENT_ADMIN_ACCESS nếu observation thực sự phù hợp; hiện UNKNOWN. Cần policy owner ký explicit admin read entitlement; nếu thêm vào cohort phải tạo revision mới, không tự chọn DENY hoặc ALLOW.
3. Sáu ô profile: chấp nhận PUBLIC/ALLOW từ allowlist và GET OpenAPI không security (đã kiểm không global security). ownership có user_profile owner không làm endpoint private. Public response không phải authorized shared-private và không tự là BOLA. Sensitive field ngoài public contract cần review exposure riêng.
4. Ba ô /me: ALLOW là authentication/identity control. Không object-owner baseline, không suy TN BOLA. Phải kiểm username/role thực tế theo principal, không chỉ status.
5. Tất cả truth UNKNOWN; observation_source trống; NOT_RUN. Đã review policy expectation không có nghĩa đã xác nhận vulnerability truth. Denominator hiện 0, TP/FP/FN/TN và metrics null.

## Alias và canonical mapping

Book SELF/OTHER owner aliases khớp owner_alias_registry; actor aliases book và /me khớp alias_registry. Sáu profile actor aliases khác registry chính: worksheet ghi explicit case actor → role → planned principal_alias. Chấp nhận có điều kiện cho identity scenario tĩnh, không coi là sáu người mới hoặc tăng role count. Cần QA và operator xác minh nhiều alias cùng role thực sự cùng principal trước run; cấm join observation theo role/template đơn lẻ. Join exact case_id + revision + fixture slot/hash + execution/method. Contract case_manifest.py loại duplicate scenario theo method/template/actor/role/owner/category, chưa chứa fixture_hash: do đó tách alias là workaround được ghi nhận, không tự hợp nhất alias trong cohort cũ. Nếu sửa contract thêm discriminator hoặc đổi alias thì revision/case IDs mới và review lại.

5-role worksheet có 25 ô nhưng 10 ô userC/admin2 không có policy nguồn, hai ô admin/book unresolved. Chưa có 5-role canonical cohort hoặc verified principals. Không tuyên bố 3/5 roles đã thực nghiệm.

## Baseline validity và comparator gate

Baseline hợp lệ cần cùng execution, fixture snapshot/resource, owner principal đã xác minh, 2xx JSON đầy đủ đúng object/owner và protected field có giá trị hợp lệ; reject missing/null/empty protected field, error payload, truncation, parse failure, stale snapshot, wrong owner. Ghi INVALID_TEST/inconclusive và exclusion khi không đạt; không biến thành PASS/TN. So sánh status, content type, shape/length, nested normalized equality và protected-value owner match trong bộ nhớ. Length/similarity hoặc 200 không đủ xác nhận. Dynamic normalization chỉ timestamp/request_id/created_at/updated_at đã pin; không bỏ owner/id/secret và không sort array vô điều kiện. Evidence chỉ field paths, booleans và sanitized digest/ref; không secret/raw body/header.

Source review response_comparator.py: owner_control hiện chỉ dùng 2xx; analyze_all chọn baseline bằng operation_id/resource_id không gate baseline validity; _sensitive_matches có thể coi null hoặc key baseline thiếu (get trả None) là match. request_runner.py dùng urlopen mặc định redirect, response.read không bound trước khi cắt parse, generic response_json có thể chứa secret. Đây là gap source-level, không phải chứng cứ exploit đã chạy. Adapter phải gate chặt trước khi gọi comparator/persist; không tái dùng preflight hiện có vì GET / nằm ngoài năm path. Không đánh dấu CONFIRMED từ comparator legacy khi baseline chưa đạt.

## Mapping controls và exclusions

M-01 → case owner userA/bookA; M-02 → userB/bookA; M-03 → userA/bookB; M-07 → /me userA: mapping tĩnh được duyệt, historical observations không được nhập tự động. M-04 anonymous và M-05 invalid-token nằm ngoài enabled actor set/cohort, chỉ auth controls và chỉ chạy nếu có budget/approval riêng. M-06 anonymous profile ngoài cohort, public observation. Owner userB, cả sáu profile theo actor của cohort và /me userB/admin cần observation mới, không suy từ manual sample. Sharing loại MISSING_SHARING_POLICY_FIXTURE. BFLA/write/disposable và DB proof ngoài GET cohort. ZAP ILLEGAL không map trực tiếp thành CONFIRMED; public và identity controls không góp TN BOLA. Owner controls báo riêng, không dùng tăng TN; chỉ chấm BOLA khi independent observed truth, executed prediction, baseline hợp lệ và exact linkage cùng cohort.

## Gates còn thiếu và bàn giao

- QA độc lập worksheet, alias workaround và comparator guard; policy owner quyết định admin/book hoặc chấp nhận exclusions bằng nguồn có version.
- Operator artifact hiện tại pin exact target/GET paths/roles, validity window, cap và execution/output IDs; target lịch sử 100.106.64.21:5003 khác proposal loopback:5000. Không suy quyền/reachability từ lịch sử.
- Runtime snapshot tương đương fixture/OpenAPI, >=3 verified principals, owner evidence; context/attestation và exact users/rules được review riêng. Không login/seed để tự đóng gate.
- Bounded adapter + QA độc lập; ZAP enforced cap/accounting không được thay bằng MAX_MESSAGES/history guard hay timeout. Budget 30 của plan chỉ proposal, chưa approved. Tính cả baselines/identity/controls; auth ngoài GET scope cần scope riêng hoặc input đã xác minh.
- Truth quan sát độc lập và receipts exact binding mới được scoring/import; BFLA DB before/after proof vẫn UNKNOWN; Browser E2E còn BLOCKED theo bàn giao, không đóng bằng offline review.

## Ticket CMP07-ADAPTER-01 đề xuất giao owner T18

Scope: tools/authorization-lab read_only bounded adapter mới + tests riêng; Lead phân quyền file trước triển khai. Không sửa web để import/call CLI; không chạy lab trong ticket triển khai. Input frozen cohort/manifest + explicit case→fixture URL/actor mapping (bao gồm sáu profile alias), approval/budget và verified principal context. Reject unknown/missing/duplicate case, changed digest, target/path/query/fragment/method ngoài scope, unresolved admin và alias/principal mismatch.

Dry-plan offline xuất exact GET sequence, baseline/control reuse có nguồn, cap tổng và cap từng phase; chỉ năm paths, không GET /, không preflight cũ, không auto login/recovery. Run transport concurrency 1, retry 0, reject redirect trước follow, count trước dispatch kể cả failure, cancel/timeout và hard body read bound. Stop trước request vượt cap; không fallback vào runner rộng. Owner/identity gates như trên phải chạy trước kết luận. Raw protected values chỉ trong bộ nhớ, redact trước artifacts/logs/errors. Receipt schema2 bind exact case/cohort/fixture/source/execution, status NOT_RUN/INVALID_TEST/inconclusive rõ lý do; thiếu timing null/status, không 0. Không tự nhập observation legacy.

Acceptance offline bằng fake transport: deny foreign origin/path/redirect; count identity/baseline/error đúng; cap exhaustion/cancel không thêm request; wrong owner, baseline 401/500, truncated/non-JSON/error 200, null/empty/missing secret và equal generic error không CONFIRMED; nested owner secret match chỉ CONFIRMED khi DENY + valid baseline; dynamic fields không mất owner, public ALLOW không BOLA, admin unresolved excluded; zero raw secrets trong receipt/output; schema2 roundtrip và exact linkage; dry-plan không network/DNS/process. QA độc lập sau bàn giao. Ticket runtime CMP07-RUN-01 chỉ mở sau gates, không nằm trong quyền review này.
